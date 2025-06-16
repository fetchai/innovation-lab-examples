"""
Enhanced Nike Product Scraper functions and data models.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file
from typing import Optional, List, Dict, Any
from enum import Enum as PythonEnum

from notte_sdk import NotteClient, RemoteSession, retry
from pydantic import BaseModel, Field
from uagents import Model
from urllib.parse import urljoin

# Config
RESULT_DIR = Path("nike_results")
NOTTE_API_KEY = os.environ.get("NOTTE_API_KEY", "")
NIKE_BASE_URL = "https://www.nike.com"

# ############################################
# ENUMS and MODELS for Scraping Logic
# ############################################

class GenderTarget(str, PythonEnum):
    MEN = "men"
    WOMEN = "women"
    KIDS = "kids"
    UNISEX = "unisex"

class SortOption(str, PythonEnum):
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NEWEST = "newest"
    BEST_SELLING = "best_selling"
    RELEVANCE = "relevance" # Default for search

class ProductCategory(BaseModel):
    name: str = Field(description="The name of the product category")
    url: str = Field(description="The URL of the product category")
    menu: Optional[str] = Field(None, description="The menu group of the product category (e.g., 'Shoes', 'Clothing')")
    parent_category: Optional[str] = Field(None, description="The parent category if this is a sub-category")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Any filters applied to get this category list (e.g., color, size)")

class ProductCategories(BaseModel):
    categories: List[ProductCategory]
    source_url: str = Field(description="The URL from which these categories were scraped")

    @staticmethod
    def example():
        return ProductCategories(
            categories=[
                ProductCategory(name="Running Shoes", menu="Shoes", url=f"{NIKE_BASE_URL}/w/mens-running-shoes-37v7jzy7ok"),
                ProductCategory(name="Lifestyle Sneakers", menu="Shoes", url=f"{NIKE_BASE_URL}/w/mens-lifestyle-shoes-13jrmznik1"),
                ProductCategory(name="Basketball Shorts", menu="Clothing", parent_category="Shorts", url=f"{NIKE_BASE_URL}/w/mens-basketball-shorts-38fphz98uk"),
            ],
            source_url=f"{NIKE_BASE_URL}/men"
        )

class ShoppingItem(BaseModel):
    name: str = Field(description="The name of the product")
    price: Optional[float] = Field(None, description="The price of the product. Can be null if price varies or is not listed.")
    original_price: Optional[float] = Field(None, description="The original price if the item is on sale")
    currency: str = Field("USD", description="Currency of the price (e.g., USD, EUR)")
    url: str = Field(description="The URL of the product page")
    image_src: Optional[str] = Field(None, description="The URL or src path to the product image")
    category: Optional[str] = Field(None, description="The category the product belongs to")
    product_id: Optional[str] = Field(None, description="Unique product identifier if available")
    available_sizes: Optional[List[str]] = Field(None, description="List of available sizes")
    color: Optional[str] = Field(None, description="Primary color of the product shown")
    rating: Optional[float] = Field(None, description="Average customer rating (e.g., 4.5)")
    review_count: Optional[int] = Field(None, description="Number of customer reviews")

class ShoppingList(BaseModel):
    items: List[ShoppingItem]
    category_scraped: Optional[str] = Field(None, description="The specific category these items belong to")
    total_items_found: Optional[int] = Field(None, description="Total items found for the query, even if not all are listed")
    current_page: Optional[int] = Field(1, description="Current page number if paginated")
    total_pages: Optional[int] = Field(None, description="Total pages available if paginated")
    source_url: str = Field(description="The URL from which these items were scraped")

# ############################################
# Request/Response Models for uAgent
# ############################################

class NikeAction(str, PythonEnum):
    # Category focused
    GET_MAIN_CATEGORIES = "get_main_categories" # e.g., Men's Shoes, Women's Clothing
    GET_SUB_CATEGORIES = "get_sub_categories"   # e.g., Men's Running Shoes under Men's Shoes
    # Product focused
    LIST_PRODUCTS_BY_CATEGORY = "list_products_by_category"
    SEARCH_PRODUCTS = "search_products" # General search by keyword
    GET_PRODUCT_DETAILS = "get_product_details" # For a specific product URL or name
    # Potentially more complex
    FIND_BESTSELLERS = "find_bestsellers" # In a category or overall
    FIND_NEW_ARRIVALS = "find_new_arrivals" # In a category or overall
    # Simplified for direct use / backward compatibility
    LIST_CATEGORIES = "list_categories" # Alias for GET_MAIN_CATEGORIES
    LIST_PRODUCTS = "list_products" # Alias for LIST_PRODUCTS_BY_CATEGORY (default to men's general)

class NikeScrapeRequest(Model):
    action: NikeAction
    category_name: Optional[str] = None
    sub_category_name: Optional[str] = None
    gender: Optional[GenderTarget] = GenderTarget.MEN
    search_term: Optional[str] = None
    product_url: Optional[str] = None
    product_name_for_details: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    sort_by: Optional[SortOption] = None
    page_number: Optional[int] = 1
    max_items: Optional[int] = 10

class NikeScrapeResponse(Model):
    results: str # This will contain the formatted string response
    # Optional raw structured data for debugging or complex use cases, not sent to user by default
    raw_data: Optional[Dict[str, Any]] = None

# ############################################
# Helper Functions
# ############################################

def _build_nike_url(
    gender: GenderTarget = GenderTarget.MEN,
    category_path: Optional[str] = None, # e.g., "w/mens-running-shoes-37v7jzy7ok" or "w/new-3n82y"
    search_query: Optional[str] = None,
    filters: Optional[Dict[str, str]] = None, # e.g. {"color": "blue", "size": "10"}
    sort_by: Optional[SortOption] = None,
    page: Optional[int] = None
) -> str:
    """Constructs a Nike URL based on provided parameters."""
    if search_query:
        base = f"{NIKE_BASE_URL}/w?q={search_query.replace(' ', '%20')}"
    elif category_path:
        if category_path.startswith("/"):
            base = f"{NIKE_BASE_URL}{category_path}"
        else:
            base = f"{NIKE_BASE_URL}/{category_path}"
    else:
        base = f"{NIKE_BASE_URL}/{gender.value}"

    params = []
    if filters:
        # Nike uses a specific format for filters, often like /color-blue/size-10
        # This is a simplified version, actual Nike filter params can be complex
        # For now, we'll assume filters are appended if the Notte agent is instructed to apply them
        pass # Placeholder for more complex filter URL construction if needed

    if sort_by:
        # Nike sort params vary, e.g., "&sort=priceAsc" or part of path
        # For now, we'll assume Notte agent handles sorting via instructions
        pass # Placeholder

    if page and page > 1:
        # Nike pagination can be /page/2 or ?page=2
        # Assuming Notte agent handles this via instructions for now
        pass # Placeholder

    query_string = "&amp;".join(params)
    return f"{base}{'?' if query_string and '?' not in base else ''}{'&amp;' if query_string and '?' in base else ''}{query_string}"

async def _scrape_nike_data_with_notte(
    url: str,
    task_description: str,
    output_model: type[BaseModel],
    session: RemoteSession,
    max_steps: int = 25 # Increased default max_steps
) -> Optional[BaseModel]:
    """Generic function to scrape data from a Nike URL using Notte agent and parse to a Pydantic model."""
    try:
        print(f"Attempting to scrape URL: {url} with task: {task_description[:100]}...")
        response = NotteClient(api_key=NOTTE_API_KEY).Agent(session=session, max_steps=max_steps).run(
            task=task_description,
            url=url,
        )

        if response.answer:
            # print(f"Raw Notte response for {url}: {response.answer[:500]}...") # For debugging
            try:
                # Attempt to directly validate if the response is already the model's JSON
                return output_model.model_validate_json(response.answer)
            except Exception as val_err_direct:
                # If direct validation fails, try to find JSON within a markdown code block
                import re
                import json
                match = re.search(r"```json\n(.*?)\n```", response.answer, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    try:
                        return output_model.model_validate_json(json_str)
                    except Exception as val_err_md:
                        print(f"Error validating JSON from markdown for {url}: {val_err_md}. JSON string: {json_str[:200]}...")
                        return None
                else:
                    print(f"Error validating direct JSON for {url}: {val_err_direct}. No markdown JSON found. Answer: {response.answer[:200]}...")
                    return None
        else:
            print(f"No answer received from Notte agent for URL: {url}. Error: {response.error if hasattr(response, 'error') else 'Unknown'}")
            return None
    except Exception as e:
        print(f"Exception during Notte scraping for {url}: {e}")
        return None

# ############################################
# Scraping Functions (using the new models)
# ############################################

@retry(max_tries=3)
async def scrape_main_categories(session: RemoteSession, gender: GenderTarget = GenderTarget.MEN) -> Optional[ProductCategories]:
    """Fetch main Nike product categories for a given gender.""" 
    target_url = _build_nike_url(gender=gender)
    task = f"""
1. Go to {target_url}.
2. If a cookie consent popup appears, accept it.
3. If a location or country selector popup appears, select 'United States' or 'US'.
4. Identify the primary navigation menu, which typically appears near the top of the page or is clearly marked. From this menu, extract the main product categories relevant to '{gender.value}'. These are usually top-level, distinct links such as 'Shoes', 'Clothing', 'Accessories'. Also look for prominent sections like 'New Arrivals' or 'Sale' if they appear as main categories. Focus on links that lead to broad collections of products. Avoid extracting links from deep sub-menus, footers, or utility links (like 'Help' or 'Order Status') at this stage.
5. For each main category identified, provide its name and direct URL. If a category is part of a clear, high-level menu group (e.g., 'Featured' often groups 'New Arrivals'), include that group name as 'menu'. For standalone main categories like 'Shoes', the 'menu' field can be null or omitted if not applicable.
Return the response in a JSON format matching this schema: ```{ProductCategories.model_json_schema()}```
Make sure the 'source_url' field in the response is set to '{target_url}'.
Example of a successful output category item: {{"name": "Men's New Arrivals", "url": "{NIKE_BASE_URL}/w/mens-new-arrivals-3n82y", "menu": "Featured"}}
"""
    return await _scrape_nike_data_with_notte(target_url, task, ProductCategories, session)

@retry(max_tries=2) # Products can be more volatile
async def scrape_products_by_category(
    category_url: str, 
    category_name: str, 
    session: RemoteSession, 
    max_items: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[SortOption] = None
) -> Optional[ShoppingList]:
    """Scrapes products for a single category URL."""
    filter_instructions = ""
    if filters:
        filter_str = ", ".join([f"{k} as {v}" for k,v in filters.items()])
        filter_instructions = f"Apply filters: {filter_str}. "
    
    sort_instructions = ""
    if sort_by:
        sort_instructions = f"Sort the products by {sort_by.name.lower().replace('_', ' ')}. "

    task = f"""
1. Go to the category page: {category_url}.
2. If a cookie consent popup appears, accept it.
3. {filter_instructions}{sort_instructions}Extract the first {max_items} products from the '{category_name}' category.
4. For each product, extract its name, price (if available, as a float), original price (if on sale), currency (default 'USD'), product page URL, and image source URL.
   Also try to extract product ID, available sizes, primary color, customer rating, and review count if readily available.
5. Return the response in a JSON format matching this schema: ```{ShoppingList.model_json_schema()}```
   Ensure 'category_scraped' is '{category_name}', 'source_url' is '{category_url}', 'total_items_found' is the total number of products on the page/category if visible, and 'current_page' is 1.
Example of a successful shopping item: {{"name": "Nike Air Max 1", "price": 150.00, "currency": "USD", "url": "{NIKE_BASE_URL}/t/air-max-1-mens-shoes-2x0ljN/FZ0628-100", "image_src": "https://static.nike.com/a/images/t_PDP_1728_v1/f_auto,q_auto:eco/u_126ab356-44d8-4a06-89b4-fcdcc8df0245,c_scale,fl_relative,w_1.0,h_1.0,fl_layer_apply/1c8d8195-7bff-4b4a-94cb-535964ed3509/air-max-1-mens-shoes-2x0ljN.png"}}
"""
    return await _scrape_nike_data_with_notte(category_url, task, ShoppingList, session)

@retry(max_tries=2)
async def search_nike_products(
    search_term: str, 
    session: RemoteSession, 
    gender: GenderTarget = GenderTarget.MEN, 
    max_items: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[SortOption] = None
) -> Optional[ShoppingList]:
    """Searches for products on Nike.com."""
    target_url = _build_nike_url(search_query=search_term, gender=gender) # Search URL might not always include gender directly
    
    filter_instructions = ""
    if filters:
        filter_str = ", ".join([f"{k} as {v}" for k,v in filters.items()])
        filter_instructions = f"After searching, if possible, apply filters: {filter_str}. "

    sort_instructions = ""
    if sort_by:
        sort_instructions = f"Sort the search results by {sort_by.name.lower().replace('_', ' ')}. "

    task = f"""
1. Go to Nike.com and search for '{search_term}'. You can use this URL as a starting point: {target_url}
2. If a cookie consent popup appears, accept it. Consider results for {gender.value} if applicable.
3. {filter_instructions}{sort_instructions}Extract the first {max_items} products from the search results.
4. For each product, extract its name, price (if available, as a float), original price (if on sale), currency (default 'USD'), product page URL, and image source URL.
   Also try to extract product ID, available sizes, primary color, customer rating, and review count if readily available.
5. Return the response in a JSON format matching this schema: ```{ShoppingList.model_json_schema()}```
   Ensure 'category_scraped' is 'Search results for: {search_term}', 'source_url' is the search results page URL, 'total_items_found' is the total number of products found if visible, and 'current_page' is 1.
"""
    return await _scrape_nike_data_with_notte(target_url, task, ShoppingList, session)

@retry(max_tries=2)
async def scrape_product_details(product_url_or_name: str, session: RemoteSession, is_url: bool) -> Optional[ShoppingItem]:
    """Fetches detailed information for a single Nike product, either by URL or by searching its name."""
    target_url = product_url_or_name if is_url else _build_nike_url(search_query=product_url_or_name)
    
    initial_step = f"Go to the product page: {target_url}." if is_url else f"Search for the product '{product_url_or_name}' on Nike.com (you can start at {target_url}) and navigate to its main product page."

    task = f"""
1. {initial_step}
2. If a cookie consent popup appears, accept it.
3. Extract detailed information for this product: name, price (as a float), original price (if on sale), currency (default 'USD'), product page URL (confirm it's the correct one), image source URL, product ID (style code or SKU), all available sizes, primary color and other available colors if listed, detailed description, customer rating, and review count.
4. Return the response in a JSON format matching this schema: ```{ShoppingItem.model_json_schema()}```
   Ensure the 'url' field is the canonical product page URL.\n"""
    return await _scrape_nike_data_with_notte(target_url, task, ShoppingItem, session)

async def scrape_sub_categories(
    main_category_url: str,
    main_category_name: str,
    session: RemoteSession,
    gender: GenderTarget,
) -> Optional[ProductCategories]:
    """
    Scrapes sub-categories from a given main category page URL.
    """
    task_description = (
        f"You are on the Nike '{main_category_name}' page for {gender.value} at {main_category_url}. "
        "Your goal is to identify and extract all sub-category links visible on this page. "
        "These might be in a sidebar menu, a top navigation bar specific to this section, or within the main content area. "
        "For each sub-category, extract its name (link text) and its full URL (href). "
        "Return the data as a JSON object with a 'categories' list, where each item has 'name' and 'url'. "
        "Example: {'categories': [{'name': 'Running Shoes', 'url': '...'}, {'name': 'Lifestyle', 'url': '...'}]}"
    )
    try:
        # Define a Pydantic model for the expected raw output from Notte for this task
        class NotteSubCategory(BaseModel):
            name: str
            url: str

        class NotteSubCategoryList(BaseModel):
            categories: List[NotteSubCategory]

        raw_scraped_data = await _scrape_nike_data_with_notte(
            url=main_category_url,
            task_description=task_description,
            output_model=NotteSubCategoryList,
            session=session,
            max_steps=20 
        )

        if raw_scraped_data and raw_scraped_data.categories:
            sub_categories_list = []
            for cat_data in raw_scraped_data.categories:
                cat_url = cat_data.url
                if not cat_url.startswith("http"):
                    cat_url = urljoin(NIKE_BASE_URL, cat_url)
                
                sub_categories_list.append(
                    ProductCategory(
                        name=cat_data.name,
                        url=cat_url,
                        parent_category=main_category_name,
                        menu=main_category_name 
                    )
                )
            if not sub_categories_list: # If parsing resulted in an empty list but raw_data had categories
                print(f"Sub-category parsing resulted in empty list for {main_category_name} at {main_category_url}, though Notte might have returned data.")
                return None
            return ProductCategories(categories=sub_categories_list, source_url=main_category_url)
        else:
            print(f"No sub-categories found or failed to parse for {main_category_name} at {main_category_url}")
            return None
    except Exception as e:
        print(f"Error scraping sub-categories for {main_category_name} from {main_category_url}: {e}")
        return None

# ############################################
# Main uAgent Request Handler Function
# ############################################

async def get_nike_info_enhanced(request: NikeScrapeRequest) -> NikeScrapeResponse:
    """Main function to handle Nike scraping requests using Notte SDK with headless=False sessions."""
    if not NOTTE_API_KEY:
        return NikeScrapeResponse(results="Error: NOTTE_API_KEY is not set. Please configure it.")

    notte = NotteClient(api_key=NOTTE_API_KEY)
    response_str = "Could not process the request. Please try again."
    raw_data_response: Optional[Dict[str, Any]] = None

    try:
        # Use headless=False for all Notte sessions as per previous successful patterns
        with notte.Session(headless=False) as session:
            action = request.action
            max_items_to_return = request.max_items if request.max_items and request.max_items > 0 else 5

            if action == NikeAction.GET_MAIN_CATEGORIES or action == NikeAction.LIST_CATEGORIES:
                categories_data = await scrape_main_categories(session=session, gender=request.gender)
                if categories_data and categories_data.categories:
                    response_str = f"Found {len(categories_data.categories)} main categories for {request.gender.value} from {categories_data.source_url}:\n"
                    response_str += "\n".join([f"- {cat.name} ({cat.menu if cat.menu else 'General'}) - URL: {cat.url}" for cat in categories_data.categories[:max_items_to_return]])
                    if len(categories_data.categories) > max_items_to_return:
                        response_str += f"\n... and {len(categories_data.categories) - max_items_to_return} more."
                    raw_data_response = categories_data.model_dump()
                else:
                    response_str = f"No main categories found for {request.gender.value} or an error occurred."
            
            elif action == NikeAction.LIST_PRODUCTS_BY_CATEGORY or action == NikeAction.LIST_PRODUCTS:
                category_to_process = request.category_name.strip() if request.category_name else None
                actual_category_name_found = None # To store the name of the category as found on Nike's site
                target_category_url = None # Initialize target_category_url here

                # Clean category_to_process by removing gender specifics if gender is set
                if category_to_process and request.gender:
                    gender_val_lower = request.gender.value.lower()
                    prefixes_to_remove = [
                        f"{gender_val_lower}'s ", 
                        f"{gender_val_lower} ", 
                        # Add common variations if needed, e.g., 'male ', 'female '
                    ]
                    for prefix in prefixes_to_remove:
                        if category_to_process.lower().startswith(prefix):
                            category_to_process = category_to_process[len(prefix):].strip()
                            print(f"Cleaned category_to_process to: '{category_to_process}' after removing gender prefix '{prefix.strip()}'")
                            break

                # If action is LIST_PRODUCTS_BY_CATEGORY, category_name is mandatory
                if action == NikeAction.LIST_PRODUCTS_BY_CATEGORY and not category_to_process:
                    response_str = "Error: Category name is required for listing products by category."
                    return NikeScrapeResponse(results=response_str, raw_data=raw_data_response)

                if not category_to_process: # Implies action == NikeAction.LIST_PRODUCTS and no category given
                    print(f"No category specified for LIST_PRODUCTS. Attempting to find a default like 'New Arrivals' for {request.gender.value}.")
                    main_categories_data = await scrape_main_categories(session=session, gender=request.gender)
                    if main_categories_data and main_categories_data.categories:
                        # Try to find 'New Arrivals', 'New Releases', etc.
                        for cat_pattern in ["new arrivals", "new releases", "latest", "just in"]:
                            for cat in main_categories_data.categories:
                                if cat_pattern in cat.name.lower():
                                    target_category_url = cat.url
                                    actual_category_name_found = cat.name 
                                    print(f"Found default category: '{actual_category_name_found}' at {target_category_url}")
                                    break
                            if target_category_url: break
                        
                        # Fallback: if no 'new' type category, try a general one like 'Shoes' or 'Clothing'
                        if not target_category_url:
                            for cat_pattern in ["shoes", "clothing", "shop all", "all products"]:
                                for cat in main_categories_data.categories:
                                    if cat_pattern in cat.name.lower():
                                        target_category_url = cat.url
                                        actual_category_name_found = cat.name
                                        print(f"Found fallback default category: '{actual_category_name_found}' at {target_category_url}")
                                        break
                                if target_category_url: break
                        
                        if not target_category_url and main_categories_data.categories: # Still nothing, take the very first one
                            target_category_url = main_categories_data.categories[0].url
                            actual_category_name_found = main_categories_data.categories[0].name
                            print(f"Using first main category as default: '{actual_category_name_found}' at {target_category_url}")
                    
                    if not target_category_url:
                        response_str = f"Error: Could not determine a default category (e.g., New Arrivals) for {request.gender.value} to list products."
                        return NikeScrapeResponse(results=response_str, raw_data=raw_data_response)
                
                else: # A category_name was provided (either by user or set by previous default logic if it were structured differently)
                    # Attempt to find the URL for the given category_to_process
                    main_categories_data = await scrape_main_categories(session=session, gender=request.gender)
                    if main_categories_data and main_categories_data.categories:
                        for cat in main_categories_data.categories:
                            if category_to_process.lower() in cat.name.lower():
                                target_category_url = cat.url
                                actual_category_name_found = cat.name
                                print(f"Found '{actual_category_name_found}' as a main category. URL: {target_category_url}")
                                break
                    
                    if not target_category_url and main_categories_data and main_categories_data.categories:
                        print(f"'{category_to_process}' not found as a main category. Checking sub-categories...")
                        for main_cat in main_categories_data.categories:
                            print(f"Checking sub-categories under '{main_cat.name}' for '{category_to_process}'...")
                            sub_categories_data = await scrape_sub_categories(
                                main_category_url=main_cat.url,
                                main_category_name=main_cat.name,
                                session=session,
                                gender=request.gender
                            )
                            if sub_categories_data and sub_categories_data.categories:
                                for sub_cat in sub_categories_data.categories:
                                    if category_to_process.lower() in sub_cat.name.lower():
                                        target_category_url = sub_cat.url
                                        actual_category_name_found = sub_cat.name
                                        print(f"Found '{actual_category_name_found}' as a sub-category under '{main_cat.name}'. URL: {target_category_url}")
                                        break  # Found the sub-category
                            if target_category_url:  # If found in current main_cat's sub-categories
                                break
                
                if target_category_url and actual_category_name_found:
                    print(f"Proceeding to scrape products from: '{actual_category_name_found}' at {target_category_url}")
                    products_data = await scrape_products_by_category(
                        category_url=target_category_url,
                        category_name=actual_category_name_found,
                        session=session,
                        max_items=max_items_to_return,
                        filters=request.filters,
                        sort_by=request.sort_by
                    )
                    if products_data and products_data.items:
                        response_str = f"Found {len(products_data.items)} products in {request.gender.value}'s '{actual_category_name_found}' (from {products_data.source_url}):\n"
                        for prod in products_data.items: # Already limited by max_items in scrape_products_by_category
                            price_str = f"Price: {prod.price}" if prod.price else "Price not available"
                            response_str += f"- {prod.name} - {price_str} - URL: {prod.url}\n"
                        if products_data.total_items_found and products_data.total_items_found > len(products_data.items):
                            response_str += f"... and more products available (total ~{products_data.total_items_found})."
                        raw_data_response = products_data.model_dump()
                    else:
                        response_str = f"No products found for {request.gender.value}'s '{actual_category_name_found}' at {target_category_url}, or an error occurred during scraping."
                else:
                    response_str = f"Error: Could not find the category URL for '{category_to_process if category_to_process else 'the default category'}' for {request.gender.value}. Please check the category name or try a broader query."
            
            elif action == NikeAction.SEARCH_PRODUCTS:
                if not request.search_term:
                    return NikeScrapeResponse(results="Error: Search term is required for searching products.")
                
                search_results = await search_nike_products(
                    search_term=request.search_term,
                    session=session,
                    gender=request.gender,
                    max_items=max_items_to_return,
                    filters=request.filters,
                    sort_by=request.sort_by
                )
                if search_results and search_results.items:
                    response_str = f"Found {len(search_results.items)} products (showing up to {max_items_to_return}) for search term '{request.search_term}' from {search_results.source_url}:\n"
                    for item in search_results.items:
                        price_info = f"${item.price:.2f}" if item.price is not None else "Price not available"
                        response_str += f"- {item.name} ({price_info}) - URL: {item.url}\n"
                    if search_results.total_items_found and search_results.total_items_found > len(search_results.items):
                         response_str += f"... and {search_results.total_items_found - len(search_results.items)} more products matching this search."
                    raw_data_response = search_results.model_dump()
                else:
                    response_str = f"No products found for search term '{request.search_term}' or an error occurred."

            elif action == NikeAction.GET_PRODUCT_DETAILS:
                product_to_find = request.product_url or request.product_name_for_details
                if not product_to_find:
                    return NikeScrapeResponse(results="Error: Product URL or name is required to get details.")
                
                is_url_provided = bool(request.product_url)
                product_detail = await scrape_product_details(product_to_find, session, is_url=is_url_provided)
                
                if product_detail:
                    response_str = f"Details for {product_detail.name}:\n"
                    price_info = f"${product_detail.price:.2f} {product_detail.currency}" if product_detail.price is not None else "Price not available"
                    if product_detail.original_price and product_detail.price is not None and product_detail.original_price > product_detail.price:
                        price_info += f" (Original: ${product_detail.original_price:.2f})"
                    response_str += f"- Price: {price_info}\n"
                    response_str += f"- URL: {product_detail.url}\n"
                    if product_detail.product_id: response_str += f"- Product ID: {product_detail.product_id}\n"
                    if product_detail.color: response_str += f"- Color: {product_detail.color}\n"
                    if product_detail.available_sizes: response_str += f"- Available Sizes: {', '.join(product_detail.available_sizes)}\n"
                    if product_detail.rating: response_str += f"- Rating: {product_detail.rating}/5 ({product_detail.review_count or 0} reviews)\n"
                    if product_detail.image_src: response_str += f"- Image: {product_detail.image_src}\n"
                    # Could add description if needed, but might be too long for chat
                    raw_data_response = product_detail.model_dump()
                else:
                    response_str = f"Could not retrieve details for '{product_to_find}'."
            
            # Placeholder for GET_SUB_CATEGORIES, FIND_BESTSELLERS, FIND_NEW_ARRIVALS
            elif action == NikeAction.GET_SUB_CATEGORIES:
                if not request.category_name:
                    return NikeScrapeResponse(results="Error: Main category name (e.g., 'Shoes') is required to get sub-categories.")
                
                main_categories_data = await scrape_main_categories(session, request.gender)
                parent_category_url = None
                parent_category_name_actual = "" # Store the exact name found

                if main_categories_data and main_categories_data.categories:
                    for cat in main_categories_data.categories:
                        # Match if requested category_name is part of the found category name (e.g., "Shoes" in "Men's Shoes")
                        if request.category_name.lower() in cat.name.lower():
                            parent_category_url = cat.url
                            parent_category_name_actual = cat.name 
                            break 
                
                if parent_category_url and parent_category_name_actual:
                    sub_categories_data = await scrape_sub_categories(
                        main_category_url=parent_category_url,
                        main_category_name=parent_category_name_actual,
                        session=session,
                        gender=request.gender
                    )
                    if sub_categories_data and sub_categories_data.categories:
                        response_str = f"Found {len(sub_categories_data.categories)} sub-categories under {request.gender.value}'s '{parent_category_name_actual}' (from {sub_categories_data.source_url}):\n"
                        for sub_cat in sub_categories_data.categories:
                            response_str += f"- {sub_cat.name} - URL: {sub_cat.url}\n"
                        raw_data_response = sub_categories_data.model_dump()
                    else:
                        response_str = f"No sub-categories found for {request.gender.value}'s '{parent_category_name_actual}' at {parent_category_url}, or an error occurred during scraping/parsing."
                else:
                    response_str = f"Could not find the main category '{request.category_name}' for {request.gender.value} to look for sub-categories. Main categories found: {[c.name for c in main_categories_data.categories] if main_categories_data else 'None'}"

            # Placeholder for FIND_BESTSELLERS, FIND_NEW_ARRIVALS
            elif action in [NikeAction.FIND_BESTSELLERS, NikeAction.FIND_NEW_ARRIVALS]:
                response_str = f"Action '{action.value}' is planned but not yet fully implemented. Try asking for main categories or searching products."


            else:
                response_str = f"Unsupported action: {action.value}. Please use a supported Nike action."

    except Exception as e:
        print(f"Exception in get_nike_info_enhanced: {e}") # Log the full exception
        response_str = f"An unexpected error occurred: {str(e)[:100]}... Please check logs."
    
    return NikeScrapeResponse(results=response_str, raw_data=raw_data_response)


