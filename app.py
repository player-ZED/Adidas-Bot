from flask import Flask, request, jsonify
from urllib.parse import urlparse
import requests

app = Flask(__name__)

def extract_product_id(url):
    try:
        parsed = urlparse(url)
        path_segments = [s for s in parsed.path.split('/') if s]
        if not path_segments or not path_segments[-1].endswith('.html'):
            raise ValueError("Invalid Adidas product URL format")
        return path_segments[-1].split('.')[0]
    except Exception as e:
        raise ValueError(f"URL parsing failed: {str(e)}")

def fetch_adidas_product_data(product_url):
    try:
        product_id = extract_product_id(product_url)
        
        headers = {
            'authority': 'www.adidas.co.uk',
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
        response = requests.get(
            api_url, 
            headers=headers,
            proxies={'http': None, 'https': None},  # Bypass proxy issues
            timeout=10
        )
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

        # Main product color
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

        # Color variations
        for variation in data.get("product_link_list", []):
            if variation.get("type") == "color-variation":
                result["colors"].append({
                    "name": variation.get("search_color"),
                    "code": variation.get("productId"),
                    "image": variation.get("image")
                })
                result["images"]["color_variants"].append(variation.get("image"))

        return result

    except Exception as e:
        return {"error": str(e)}

@app.route('/get_product_data', methods=['POST'])
def product_data_endpoint():
    data = request.json
    if not data or 'product_url' not in data:
        return jsonify({"error": "Missing product_url in request"}), 400
    
    try:
        product_data = fetch_adidas_product_data(data['product_url'])
        if 'error' in product_data:
            return jsonify(product_data), 500
        return jsonify(product_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)