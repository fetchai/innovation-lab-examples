from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low
import openfoodfacts
import json
from typing import Dict, Any, List, Optional

# Define request/response models
class SearchRequest(Model):
    query: str

class ProductInfo(Model):
    code: str
    product_name: str
    brands: str
    categories: str
    image_url: str

class SearchResponse(Model):
    query: str
    count: int
    products: List[ProductInfo]
    error: Optional[str] = None

class HealthResponse(Model):
    status: str
    agent: str

# Create the product search agent
search_agent = Agent(
    name="product_search_agent",
    port=8001,
    seed="product_search_secret_seed",
    endpoint=["http://127.0.0.1:8001/submit"]
)

# Fund agent if low on balance
fund_agent_if_low(search_agent.wallet.address())

# Initialize Open Food Facts API
api = openfoodfacts.API(user_agent="uAgents-FoodSearch/1.0")

@search_agent.on_event("startup")
async def startup_event(ctx: Context):
    ctx.logger.info(f"Product Search Agent {search_agent.name} started!")
    ctx.logger.info(f"Agent address: {search_agent.address}")

@search_agent.on_rest_post("/search", SearchRequest, SearchResponse)
async def search_products(ctx: Context, req: SearchRequest) -> SearchResponse:
    """
    Search for products using text query
    Expected request format: {"query": "search_term"}
    """
    try:
        query = req.query
        ctx.logger.info(f"Searching for products with query: {query}")
        
        # Search products using Open Food Facts API
        results = api.product.text_search(query, page_size=10)
        
        # Extract relevant information
        products = []
        for product in results.get("products", [])[:10]:  # Limit to 10 results
            product_info = ProductInfo(
                code=product.get("code", "N/A"),
                product_name=product.get("product_name", "N/A"),
                brands=product.get("brands", "N/A"),
                categories=product.get("categories", "N/A"),
                image_url=product.get("image_url", "")
            )
            products.append(product_info)
        
        ctx.logger.info(f"Found {len(products)} products")
        return SearchResponse(
            query=query,
            count=results.get("count", 0),
            products=products
        )
        
    except Exception as e:
        ctx.logger.error(f"Search error: {str(e)}")
        return SearchResponse(
            query=req.query,
            count=0,
            products=[],
            error=f"Failed to search products: {str(e)}"
        )

@search_agent.on_rest_get("/health", HealthResponse)
async def health_check(ctx: Context) -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(status="healthy", agent="product_search_agent")

if __name__ == "__main__":
    search_agent.run() 