from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def extract_product_id(url):
    """Extract product ID from Adidas product URL"""
    try:
        parsed = urlparse(url)
        path_segments = [s for s in parsed.path.split('/') if s]
        if not path_segments or not path_segments[-1].endswith('.html'):
            raise ValueError("Invalid Adidas product URL format")
        return path_segments[-1].split('.')[0]
    except Exception as e:
        raise ValueError(f"URL parsing failed: {str(e)}")

def get_product_data(product_url):
    """Get complete product data from Adidas product URL"""
    try:
        product_id = extract_product_id(product_url)
        
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'priority': 'u=1, i',
            'referer': product_url,
            'sec-ch-ua': '"Not/A)Brand";v="99", "Microsoft Edge";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0',
        }

        api_url = f'https://www.adidas.co.uk/api/product-list/{product_id}'
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()[0]

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

        for variation in data.get("product_link_list", []):
            if variation.get("type") == "color-variation":
                result["colors"].append({
                    "name": variation.get("search_color"),
                    "code": variation.get("productId"),
                    "image": variation.get("image")
                })
                result["images"]["color_variants"].append(variation.get("image"))

        return json.dumps(result, indent=4)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=4)

@app.route('/api/product', methods=['POST'])
def handle_product_request():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "Missing product URL in request"}), 400
        
        product_url = data['url']
        result = get_product_data(product_url)
        return jsonify(json.loads(result)), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "Adidas Product API - Send POST requests to /api/product with a 'url' parameter"

if __name__ == '__main__':
    app.run(debug=True)
