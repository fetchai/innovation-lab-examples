# Open Food Facts uAgents Integration

This project demonstrates the integration of uAgents with the Open Food Facts API, creating a microservice architecture where specialized agents handle different types of food product requests.

## Architecture

### Two Specialized Agents
- **Search Agent** (Port 8001): Handles product search queries using `on_rest_post`
- **Info Agent** (Port 8002): Retrieves detailed product information by barcode using `on_rest_post`

### Frontend
- **Flask Web App** (Port 5000): Simple HTML interface to interact with all agents

## 🎯 Agent Information

### 🔍 Search Agent (Port 8001)
- **Purpose**: Find products by text search
- **Input**: `{"query": "search_term"}`
- **Use Case**: Discovering products by name, brand, category
- **Output**: List of matching products with basic info (name, brand, barcode)

### 📋 Info Agent (Port 8002)  
- **Purpose**: Get comprehensive details for a specific product
- **Input**: `{"barcode": "exact_barcode_string"}`
- **Use Case**: Getting full nutrition facts, ingredients, allergens
- **Output**: Complete product information (nutrition, packaging, etc.)

## 🚀 Quick Start

### 1. Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start Agents (Individual Terminals)

**Terminal 1 - Search Agent:**
```bash
source venv/bin/activate  # Activate venv if not already active
python3 product_search_agent.py
```

**Terminal 2 - Info Agent:**
```bash
source venv/bin/activate  # Activate venv if not already active
python3 product_info_agent.py
```

**Terminal 3 - Frontend:**
```bash
source venv/bin/activate  # Activate venv if not already active
python3 frontend_app.py
```

### 4. Access the Interface
Open your browser to: http://127.0.0.1:5000

## 🧪 Testing with cURL

### Search for Products
```bash
curl -X POST http://127.0.0.1:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "chocolate"}'
```

### Get Product Details
```bash
curl -X POST http://127.0.0.1:8002/product \
  -H "Content-Type: application/json" \
  -d '{"barcode": "3017620422003"}'
```

## 📡 API Endpoints

### Search Agent (Port 8001)
- `POST /search` - Search for products
  - Body: `{"query": "search_term"}`
- `GET /health` - Health check

### Info Agent (Port 8002)  
- `POST /product` - Get product details
  - Body: `{"barcode": "barcode_string"}`
- `GET /health` - Health check

## 📁 Project Structure

```
├── requirements.txt              # Dependencies
├── product_search_agent.py       # Search agent (POST /search)
├── product_info_agent.py         # Info agent (POST /product)  
├── frontend_app.py               # Flask web application
├── templates/
│   └── index.html               # Web interface
└── README.md                    # This file
```

## 🔧 Technical Notes

### Data Flow
1. **Search**: Text query → Multiple product matches
2. **Info**: Exact barcode → Single product details  

### Input Formats
- **Search Agent**: Only needs a search query string
- **Info Agent**: Only needs a barcode string  

## 🎯 Use Cases

1. **Product Discovery**: Search by keywords to find products
2. **Product Analysis**: Get detailed nutrition and ingredient data
3. **System Monitoring**: Check health status of all services

## 🔍 Example Workflows

### Finding a Product
1. Search for "organic pasta" → Get list of products
2. Pick a barcode from results → Get detailed info

### Product Information Pipeline
```
User Query → Search Agent → Product List → Info Agent → Full Details
```

## 🚨 Error Handling

- All agents validate input parameters
- Comprehensive error messages with request details
- Graceful handling of API failures
- Frontend displays user-friendly error messages
- Frontend requests to local agents use a 5-second timeout so stalled agents return controlled JSON errors instead of hanging the UI

## 🛠️ Technical Details

### uAgents Framework
- Uses `on_rest_post` decorators for all data endpoints
- Context-based request handling with proper validation
- Automatic agent funding and address generation

### Open Food Facts Integration
- Direct HTTP requests to Open Food Facts API with proper User-Agent headers
- Rate limiting compliance
- Comprehensive product data extraction

---

**Ready to explore? Start the agents in separate terminals and open the web interface! 🚀**
