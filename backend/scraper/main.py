import asyncio
from playwright.async_api import async_playwright
import json
import os
from amazon import get_product as get_amazon_product
from requests import post

# Constants
AMAZON = "https://amazon.com.au"

# The key search-related elements of each website of interest
URLS = {
    AMAZON: {
        "search_field_query": 'input[name="field-keywords"]',
        "search_button_query": 'input[value="Go"]',
        "product_selector": "div.s-card-container"
    }
}

available_urls = URLS.keys()

# Search
async def search(metadata, page, search_text):
    print(f'Searching for {search_text} on {page.url}')
    search_field_query = metadata.get('search_field_query')
    search_button_query = metadata.get('search_button_query')
    
    if search_field_query and search_button_query:
        print("Filling in input fields...")
        search_box = await page.wait_for_selector(search_field_query)
        await search_box.type(search_text)
        print("Pressing search button")
        button = await page.wait_for_selector(search_button_query)
        await button.click()
    else:
        raise Exception("Search parameters not found")
    

    await page.wait_for_load_state()
    return page

# Get the product details
async def get_products(page, search_text, selector, get_product):
    print('Gathering products.')
    product_divs = await page.query_selector_all(selector)
    valid_products = []
    words = search_text.split(" ")
    
    async with asyncio.TaskGroup() as tg:
        for div in product_divs:
            async def task(p_div):
                product = await get_product(p_div)
                
                if not product["price"] or not product["url"]:
                    return
                
                # For all search words, if the product name does not exist or a certain word is not in the product name, it's not a relevant product
                for word in words:
                    if not product["name"] or word.lower() not in product["name"].lower():
                        break
                else:
                    valid_products.append(product)
            tg.create_task(task(div))
            
    return valid_products

# Save results into a JSON
def save_results(results):
    data = {"results": results}
    
    # Define the file path
    directory = os.path.join(".")  # This is the directory you want the file to be saved in
    FILE = os.path.join(directory, "results.json")

    # Make sure the directory exists, if not create it
    os.makedirs(directory, exist_ok=True)

    # Write the data to the JSON file
    with open(FILE, "w") as f:
        json.dump(data, f)

    print(f"Results saved to {FILE}")

# Post results to the BE which will get parsed in an effective format and saved to the DB
def post_results(results, endpoint, search_text, source):
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "data": results,
        "search_text": search_text,
        "source": source
    }
    
    print('Sending request to', endpoint)
    response = post('http://localhost:5000' + endpoint, headers=headers, json=data)
    print('Status code:', response.status_code);

# Main: the entry point of the program

async def main(url, search_text, response_route):
    metadata = URLS.get(url)
    if not metadata:
        print("Invalid URL")
        return

    async with async_playwright() as pw:
        # Set up the playwright browser
        print('Connecting to browser.')
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Navigate to  the provided url
        # NOTE: this page might not actually be going anywhere. Double check.
        await page.goto(url, timeout=1200000)
        print('Loaded initial page')
        search_page = await search(metadata, page, search_text)
        
        def func(x): return None
        if url == AMAZON:
            func = get_amazon_product
        else:
            raise Exception("Invalid URL")
        
        # Gather the results using the AMAZON API we created
        results = await get_products(search_page, search_text, metadata['product_selector'], func)
        
        print("Saving results.")
        save_results(results)
        #post_results(results, response_route, search_text, url)
        
        await browser.close()
        
if __name__ == '__main__':
    # test script
    asyncio.run(main(AMAZON, 'ryzen 9', ""))