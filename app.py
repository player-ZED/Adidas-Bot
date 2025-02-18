from flask import Flask, request, jsonify
from urllib.parse import urlparse
import requests
import os

app = Flask(__name__)

def extract_product_id(url):
    """Extract product ID from Adidas URL"""
    try:
        parsed = urlparse(url)
        path_segments = [s for s in parsed.path.split('/') if s]
        if not path_segments or not path_segments[-1].endswith('.html'):
            raise ValueError("Invalid Adidas URL format")
        return path_segments[-1].split('.')[0]
    except Exception as e:
        raise ValueError(f"URL parsing failed: {str(e)}")

@app.route('/scrape', methods=['POST'])
def scrape_adidas():
    try:
        # Get URL from request
        data = request.get_json()
        product_url = data.get('url')
        
        if not product_url:
            return jsonify({"error": "Missing 'url' in request body"}), 400

        # Get proxy config from environment variables
        proxy_config = {
            "host": os.getenv('PROXY_HOST'),
            "port": os.getenv('PROXY_PORT'),
            "username": os.getenv('PROXY_USERNAME'),
            "password": os.getenv('PROXY_PASSWORD')
        }

        # Configure headers
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'referer': product_url
        }

        # Get product data
        product_id = extract_product_id(product_url)
        api_url = f'https://www.adidas.co.uk/api/product-list/{product_id}'
        
        response = requests.get(
            api_url,
            headers=headers,
            proxies={
                "http": f"http://{proxy_config['username']}:{proxy_config['password']}@{proxy_config['host']}:{proxy_config['port']}",
                "https": f"http://{proxy_config['username']}:{proxy_config['password']}@{proxy_config['host']}:{proxy_config['port']}"
            },
            verify=False
        )
        
        response.raise_for_status()
        data = response.json()[0]

        # Process response data
        result = {
            "product_url": product_url,
            "title": data.get("name"),
            "price": data["pricing_information"].get("currentPrice"),
            "currency": "GBP",
            "product_code": data.get("model_number"),
            "colors": [],
            "sizes": [size.get("size") for size in data.get("variation_list", [])],
            "images": {
                "main_images": [],
                "color_variants": []
            }
        }

        # Add main product color
        main_color = data.get("attribute_list", {}).get("color")
        if main_color:
            result["colors"].append({
                "name": main_color,
                "code": product_id,
                "image": next((img["image_url"] for img in data.get("view_list", []) 
                           if img.get("type") == "other"), None)
            })
            result["images"]["main_images"] = [img["image_url"] 
                                             for img in data.get("view_list", [])]

        # Add color variations
        for variation in data.get("product_link_list", []):
            if variation.get("type") == "color-variation":
                result["colors"].append({
                    "name": variation.get("search_color"),
                    "code": variation.get("productId"),
                    "image": variation.get("image")
                })
                result["images"]["color_variants"].append(variation.get("image"))

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
