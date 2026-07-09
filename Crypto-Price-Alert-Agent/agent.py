from uagents import Agent, Context
import requests

# 1. Define your Agent
# Replace "your_seed_phrase" with any random text
crypto_agent = Agent(name="crypto_watcher", seed="Cripto_Watcher_24")

# 2. Configuration
CRYPTO_ID = "bitcoin"  # You can change this to 'ethereum' etc.
THRESHOLD_PRICE = 60000 # Alert if price goes below this

def get_price(coin_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    response = requests.get(url)
    data = response.json()
    return data[coin_id]['usd']

@crypto_agent.on_interval(period=60.0)
async def check_price(ctx: Context):
    try:
        current_price = get_price(CRYPTO_ID)
        ctx.logger.info(f"Current {CRYPTO_ID} price: ${current_price}")
        
        if current_price < THRESHOLD_PRICE:
            ctx.logger.info(f"🚨 ALERT: {CRYPTO_ID} is below ${THRESHOLD_PRICE}! Time to buy?")
        else:
            ctx.logger.info(f"Price is stable above ${THRESHOLD_PRICE}.")
            
    except Exception as e:
        ctx.logger.error(f"Failed to fetch price: {e}")

if __name__ == "__main__":
    crypto_agent.run()