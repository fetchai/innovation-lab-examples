from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low
import requests
import json
from typing import Dict, Any, Optional

# Define request/response models
class ProductRequest(Model):
    barcode: str

class ProductInfoResponse(Model):
    barcode: str
    product_name: str
    brands: str
    categories: str
    ingredients_text: str
    allergens: str
    nutrition_grades: str
    ecoscore_grade: str
    image_url: str
    countries: str
    stores: str
    packaging: str
    quantity: str
    energy_100g: str
    fat_100g: str
    sugars_100g: str
    salt_100g: str
    error: Optional[str] = None

class HealthResponse(Model):
    status: str
    agent: str

# Create the product info agent
info_agent = Agent(
    name="product_info_agent",
    port=8002,
    seed="product_info_secret_seed",
    endpoint=["http://127.0.0.1:8002/submit"]
)

# Fund agent if low on balance
fund_agent_if_low(info_agent.wallet.address())

@info_agent.on_event("startup")
async def startup_event(ctx: Context):
    ctx.logger.info(f"Product Info Agent {info_agent.name} started!")
    ctx.logger.info(f"Agent address: {info_agent.address}")

@info_agent.on_rest_post("/product", ProductRequest, ProductInfoResponse)
async def get_product_info(ctx: Context, req: ProductRequest) -> ProductInfoResponse:
    """
    Get detailed product information by barcode
    Expected request format: {"barcode": "1234567890123"}
    """
    try:
        barcode = req.barcode
        ctx.logger.info(f"Getting product info for barcode: {barcode}")
        
        # Use direct API call to Open Food Facts
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        headers = {
            'User-Agent': 'uAgents-FoodInfo/1.0 (https://github.com/fetchai/uAgents)'
        }
        
        ctx.logger.info(f"Making API call to: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            ctx.logger.error(f"API call failed with status {response.status_code}")
            return ProductInfoResponse(
                barcode=barcode,
                product_name="N/A",
                brands="N/A",
                categories="N/A",
                ingredients_text="N/A",
                allergens="N/A",
                nutrition_grades="N/A",
                ecoscore_grade="N/A",
                image_url="",
                countries="N/A",
                stores="N/A",
                packaging="N/A",
                quantity="N/A",
                energy_100g="N/A",
                fat_100g="N/A",
                sugars_100g="N/A",
                salt_100g="N/A",
                error=f"API call failed: HTTP {response.status_code}"
            )
        
        data = response.json()
        ctx.logger.info(f"API response status: {data.get('status')}")
        
        if data.get('status') != 1 or "product" not in data:
            ctx.logger.warning("Product not found in API response")
            return ProductInfoResponse(
                barcode=barcode,
                product_name="N/A",
                brands="N/A",
                categories="N/A",
                ingredients_text="N/A",
                allergens="N/A",
                nutrition_grades="N/A",
                ecoscore_grade="N/A",
                image_url="",
                countries="N/A",
                stores="N/A",
                packaging="N/A",
                quantity="N/A",
                energy_100g="N/A",
                fat_100g="N/A",
                sugars_100g="N/A",
                salt_100g="N/A",
                error="Product not found"
            )
        
        product = data["product"]
        product_name = product.get("product_name", "N/A")
        ctx.logger.info(f"Retrieved product: {product_name}")
        
        # Extract comprehensive product information
        return ProductInfoResponse(
            barcode=barcode,
            product_name=product_name,
            brands=product.get("brands", "N/A"),
            categories=product.get("categories", "N/A"),
            ingredients_text=product.get("ingredients_text", "N/A"),
            allergens=product.get("allergens", "N/A"),
            nutrition_grades=product.get("nutrition_grades", "N/A"),
            ecoscore_grade=product.get("ecoscore_grade", "N/A"),
            image_url=product.get("image_url", ""),
            countries=product.get("countries", "N/A"),
            stores=product.get("stores", "N/A"),
            packaging=product.get("packaging", "N/A"),
            quantity=product.get("quantity", "N/A"),
            energy_100g=str(product.get("nutriments", {}).get("energy_100g", "N/A")),
            fat_100g=str(product.get("nutriments", {}).get("fat_100g", "N/A")),
            sugars_100g=str(product.get("nutriments", {}).get("sugars_100g", "N/A")),
            salt_100g=str(product.get("nutriments", {}).get("salt_100g", "N/A"))
        )
        
    except requests.RequestException as e:
        ctx.logger.error(f"Network error: {str(e)}")
        return ProductInfoResponse(
            barcode=req.barcode,
            product_name="N/A",
            brands="N/A",
            categories="N/A",
            ingredients_text="N/A",
            allergens="N/A",
            nutrition_grades="N/A",
            ecoscore_grade="N/A",
            image_url="",
            countries="N/A",
            stores="N/A",
            packaging="N/A",
            quantity="N/A",
            energy_100g="N/A",
            fat_100g="N/A",
            sugars_100g="N/A",
            salt_100g="N/A",
            error=f"Network error: {str(e)}"
        )
    except Exception as e:
        ctx.logger.error(f"Product info error: {str(e)}")
        return ProductInfoResponse(
            barcode=req.barcode,
            product_name="N/A",
            brands="N/A",
            categories="N/A",
            ingredients_text="N/A",
            allergens="N/A",
            nutrition_grades="N/A",
            ecoscore_grade="N/A",
            image_url="",
            countries="N/A",
            stores="N/A",
            packaging="N/A",
            quantity="N/A",
            energy_100g="N/A",
            fat_100g="N/A",
            sugars_100g="N/A",
            salt_100g="N/A",
            error=f"Failed to get product info: {str(e)}"
        )

@info_agent.on_rest_get("/health", HealthResponse)
async def health_check(ctx: Context) -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(status="healthy", agent="product_info_agent")

if __name__ == "__main__":
    info_agent.run() 