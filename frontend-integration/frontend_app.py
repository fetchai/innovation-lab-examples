from flask import Flask, render_template, request, jsonify
import requests
import json

app = Flask(__name__)

# Agent endpoints
AGENTS = {
    "search": "http://127.0.0.1:8001",
    "info": "http://127.0.0.1:8002"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search_products', methods=['POST'])
def search_products():
    """Search products via search agent"""
    try:
        query = request.form.get('query', '').strip()
        if not query:
            return jsonify({"error": "Please provide a search query"})
        
        # Call search agent with POST request
        payload = {"query": query}
        response = requests.post(f"{AGENTS['search']}/search", json=payload)
        response.raise_for_status()
        
        # Agent returns JSON directly
        result = response.json()
        
        # Format the results for display
        formatted_results = []
        if result.get('products'):
            for product in result['products'][:10]:  # Limit to 10 results
                formatted_product = {
                    'name': product.get('product_name', 'N/A'),
                    'brands': product.get('brands', 'N/A'),
                    'barcode': product.get('code', 'N/A'),
                    'categories': product.get('categories', 'N/A'),
                    'image_url': product.get('image_url', '')
                }
                formatted_results.append(formatted_product)
        
        return jsonify({
            "success": True, 
            "count": result.get('count', 0),
            "query": query,
            "products": formatted_results
        })
        
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to connect to search agent: {str(e)}"})
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"})

@app.route('/get_product_info', methods=['POST'])
def get_product_info():
    """Get product info via info agent"""
    try:
        barcode = request.form.get('barcode', '').strip()
        if not barcode:
            return jsonify({"error": "Please provide a barcode"})
        
        # Call info agent with POST request
        payload = {"barcode": barcode}
        response = requests.post(f"{AGENTS['info']}/product", json=payload)
        response.raise_for_status()
        
        # Agent returns JSON directly
        result = response.json()
        
        # Format the result for display
        if result.get('error'):
            return jsonify({"error": result['error']})
        
        formatted_result = {
            'barcode': result.get('barcode', 'N/A'),
            'name': result.get('product_name', 'N/A'),
            'brands': result.get('brands', 'N/A'),
            'categories': result.get('categories', 'N/A'),
            'ingredients': result.get('ingredients_text', 'N/A'),
            'allergens': result.get('allergens', 'N/A'),
            'nutrition_grade': result.get('nutrition_grades', 'N/A'),
            'eco_score': result.get('ecoscore_grade', 'N/A'),
            'countries': result.get('countries', 'N/A'),
            'packaging': result.get('packaging', 'N/A'),
            'quantity': result.get('quantity', 'N/A'),
            'stores': result.get('stores', 'N/A'),
            'image_url': result.get('image_url', ''),
            'nutrition': {
                'energy_100g': result.get('energy_100g', 'N/A'),
                'fat_100g': result.get('fat_100g', 'N/A'),
                'sugars_100g': result.get('sugars_100g', 'N/A'),
                'salt_100g': result.get('salt_100g', 'N/A')
            }
        }
        
        return jsonify({"success": True, "product": formatted_result})
        
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to connect to info agent: {str(e)}"})
    except Exception as e:
        return jsonify({"error": f"Info retrieval failed: {str(e)}"})

@app.route('/health')
def health_check():
    """Check health of all agents"""
    health_status = {}
    
    for agent_name, agent_url in AGENTS.items():
        try:
            response = requests.get(f"{agent_url}/health", timeout=5)
            if response.status_code == 200:
                # Health endpoint returns JSON directly
                health_data = response.json()
                health_status[agent_name] = {"status": "healthy", "url": agent_url, "agent_info": health_data}
            else:
                health_status[agent_name] = {"status": "unhealthy", "url": agent_url}
        except:
            health_status[agent_name] = {"status": "offline", "url": agent_url}
    
    return jsonify(health_status)

if __name__ == '__main__':
    print("Starting Flask frontend...")
    print("Available endpoints:")
    print("- Main interface: http://127.0.0.1:5000")
    print("- Health check: http://127.0.0.1:5000/health")
    app.run(host='127.0.0.1', port=5000, debug=True) 