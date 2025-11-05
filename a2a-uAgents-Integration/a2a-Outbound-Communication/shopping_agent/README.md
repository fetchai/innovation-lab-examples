# Shopping Partner Agent

![uagents](https://img.shields.io/badge/uagents-4A90E2) ![a2a](https://img.shields.io/badge/a2a-000000) ![agno](https://img.shields.io/badge/agno-FF69B4) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4)

## 🛍️ Shopping Partner Agent: Your AI-Powered Product Discovery Assistant

Need help finding the perfect product? The Shopping Partner Agent is your AI-powered shopping companion, designed to discover products that precisely match your preferences. Using advanced AI and web search tools, this agent delivers detailed product recommendations with comprehensive details, reviews, and comparisons to help you make informed purchase decisions.

### What it Does

This agent helps you quickly find products from trusted e-commerce platforms without the hassle. Tell it what you need, and it suggests matching products with clear details, pricing, ratings, and direct purchase links.

## ✨ Key Features

* **Comprehensive Product Search** - Searches across Amazon, Flipkart, Myntra, Meesho, Nike, and more
* **Detailed Recommendations** - Up to 10 products with extensive details
* **Smart Matching** - Ensures at least 50% match with your requirements
* **Stock Verification** - Only recommends available products
* **Review Analysis** - Pros and cons based on customer feedback
* **Comparative Analysis** - Side-by-side comparison of top 3-5 products
* **Direct Purchase Links** - Clickable links to product pages

## 🔧 Setup

### Prerequisites

- Python 3.10 or higher (3.10.14 recommended)
- pip (Python package manager)
- Google API key for Gemini
- Exa API key for web search

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd shopping_agent
```

2. **Set Python version (if using pyenv):**
```bash
pyenv local 3.10.14
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables:**

Create a `.env` file in the project root directory with the following variables:

```env
# Google API Key (required for Gemini 2.0 Flash model)
GOOGLE_API_KEY=your_google_api_key_here

# Exa API Key (required for web search functionality)
EXA_API_KEY=your_exa_api_key_here
```

**How to get API keys:**
- **Google API Key**: Get it from [Google AI Studio](https://aistudio.google.com/app/apikey)
- **Exa API Key**: Sign up at [Exa.ai Dashboard](https://dashboard.exa.ai/)

### How to Start

Run the application with:

```bash
python main.py
```

Or if you have Python version issues:

```bash
pyenv shell 3.10.14
python main.py
```

The agent will start on the following ports:
- **Shopping Partner Specialist**: `http://localhost:10020`
- **A2A Server**: `http://localhost:9999`
- **uAgent Coordinator**: `http://localhost:8200`

**To stop the application:** Press `CTRL+C` in the terminal

### Example Query

```plaintext
Find me a durable, waterproof backpack suitable for hiking under $150 with good customer reviews.
```

### Expected Output Structure

```markdown
# Product Recommendations for Hiking Backpack

## 1. Osprey Atmos AG 65
- **Brand**: Osprey
- **Link**: [https://www.amazon.com/osprey-atmos-ag-65](https://www.amazon.com/osprey-atmos-ag-65)
- **Price**: $149.99 USD
- **Rating**: 4.7/5 stars (based on 2,300+ reviews)
- **Key Features**: 65L capacity, Anti-Gravity suspension, waterproof rain cover included, adjustable harness
- **Pros**: Excellent comfort, great ventilation, durable construction, lifetime warranty
- **Cons**: Slightly heavy, premium price point
- **Availability**: In Stock

## 2. Deuter Aircontact Lite 65+10
- **Brand**: Deuter
- **Link**: [https://www.rei.com/deuter-aircontact](https://www.rei.com/deuter-aircontact)
- **Price**: $139.95 USD
- **Rating**: 4.5/5 stars (based on 890+ reviews)
- **Key Features**: 65+10L capacity, Aircontact Lite back system, rain cover, multiple compartments
- **Pros**: Great value, comfortable fit, good organization
- **Cons**: Less premium feel than Osprey, heavier design
- **Availability**: In Stock

... (up to 10 detailed product recommendations) ...

## 📊 Comparative Analysis (Top 3)

| Feature | Osprey Atmos AG 65 | Deuter Aircontact | REI Flash 65 |
|---------|-------------------|-------------------|--------------|
| **Price** | $149.99 | $139.95 | $129.95 |
| **Rating** | 4.7/5 | 4.5/5 | 4.6/5 |
| **Weight** | 4.8 lbs | 5.2 lbs | 3.9 lbs |
| **Capacity** | 65L | 65+10L | 65L |
| **Warranty** | Lifetime | 2 years | 1 year |
| **Best For** | Comfort & durability | Budget-conscious | Lightweight hiking |
```

## 🔧 Technical Architecture

- **Framework**: uAgents + A2A Protocol + Agno Framework
- **AI Models**: Google Gemini 2.0 Flash
- **Search Engine**: Exa for intelligent web search
- **Communication**: Asynchronous agent processing
- **Timeout**: 180 seconds for complex product searches
- **Output Format**: Markdown with structured tables

## 📊 Product Details Included

Each product recommendation includes:
- **Product Name & Brand**
- **Direct Purchase Link**
- **Current Price** with currency
- **Customer Rating** from the platform
- **Key Features & Specifications**
- **Pros & Cons** from review analysis
- **Availability Status**
- **Comparative Analysis Table** (for top products)

## 🆘 Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure both Google and Exa API keys are correctly set in the `.env` file
2. **Port Conflicts**: Check if ports 10020, 8200, or 9999 are already in use. Kill them with:
   ```bash
   lsof -ti:10020,8200,9999 | xargs kill -9
   ```
3. **Python Version Error**: If you see import errors for `SingleA2AAdapter`:
   ```bash
   pyenv shell 3.10.14
   python main.py
   ```
4. **Dependency Issues**: Run `pip install -r requirements.txt` to ensure all packages are installed
5. **Exa Credit Limits**: If you exceed your credits, upgrade your plan at [Exa Dashboard](https://dashboard.exa.ai/)
6. **Timeout Errors**: Complex product searches may take up to 3 minutes (180 seconds timeout)

### Performance Tips

- Be specific about product requirements for better results
- Include price range, brand preferences, and must-have features
- The agent works best with clear, detailed queries
- Ensure stable internet connection for web scraping

## 📈 Use Cases

- **Product Research**: Find the best products in a category
- **Price Comparison**: Compare similar products across platforms
- **Gift Shopping**: Discover products based on recipient preferences
- **Budget Shopping**: Find products within a specific price range
- **Feature-Based Search**: Match products to specific requirements
- **Review Analysis**: Understand pros and cons from real customers

## 🛒 Supported Platforms

- Amazon
- Flipkart
- Myntra
- Meesho
- Google Shopping
- Nike
- And other reputable e-commerce websites

## 💡 Example Queries

```
Find wireless noise-cancelling headphones under $200 with excellent battery life
```

```
Recommend running shoes for marathon training, preferably from Nike or Adidas, size 10
```

```
Looking for a smart TV, 55 inch, 4K resolution, budget around $500-700
```

```
Find eco-friendly yoga mats with good grip and cushioning under $50
```

## 🧠 Inspired by

* [Fetch.ai uAgents](https://github.com/fetchai/uAgents)
* [Agno Framework](https://github.com/agnos-ai/agno)
* [A2A Protocol](https://a2a-protocol.org/latest/)
* [Fetch.ai Innovation Lab Examples](https://github.com/fetchai/innovation-lab-examples)
