from flask import Flask, request, jsonify
from urllib.parse import urlparse
import requests
import random
import time
import logging
import warnings
from decimal import Decimal, ROUND_HALF_UP

# Initialize Flask app
app = Flask(__name__)

# Suppress SSL warnings
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load proxies and user agents
PROXY_LIST = []
USER_AGENTS = []

def load_resources():
    """Load and convert proxies from host:port:user:pass format"""
    global PROXY_LIST, USER_AGENTS
    
    try:
        # Load and convert proxies
        with open('proxies.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if line.count(':') == 3:
                    host, port, user, pwd = line.split(':', 3)
                    PROXY_LIST.append(f"http://{user}:{pwd}@{host}:{port}")
                    logger.debug(f"Loaded proxy: {PROXY_LIST[-1]}")
            
        # Load user agents
        with open('user_agents.txt', 'r') as f:
            USER_AGENTS = [line.strip() for line in f if line.strip()]
            
        logger.info(f"Loaded {len(PROXY_LIST)} proxies and {len(USER_AGENTS)} user agents")
        
        if not PROXY_LIST:
            raise ValueError("No proxies loaded from proxies.txt")
            
    except Exception as e:
        logger.error(f"Failed to load resources: {str(e)}")
        raise

load_resources()

def extract_product_id(url):
    """Extract product ID from Adidas URL with validation"""
    try:
        parsed = urlparse(url)
        if 'adidas.co.uk' not in parsed.netloc:
            raise ValueError("Invalid domain - only adidas.co.uk supported")
            
        path_segments = parsed.path.strip('/').split('/')
        if not path_segments or not path_segments[-1].endswith('.html'):
            raise ValueError("Invalid product URL format")
            
        product_id = path_segments[-1].split('.')[0]
        if not product_id.isalnum() or len(product_id) < 5:
            raise ValueError("Invalid product ID format")
            
        return product_id
    except Exception as e:
        logger.error(f"URL parsing failed: {str(e)}")
        raise

def get_random_proxy():
    """Get random pre-formatted proxy"""
    return {
        'http': random.choice(PROXY_LIST),
        'https': random.choice(PROXY_LIST)
    }

def get_headers(referer):
    """Generate realistic browser headers"""
    return {
        'authority': 'www.adidas.co.uk',
        'accept': 'application/json',
        'accept-language': 'en-GB,en-US;q=0.9',
        'referer': referer,
        'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': random.choice(USER_AGENTS),
        'x-requested-with': 'XMLHttpRequest'
    }

def get_last_price(price_info):
    """Get the last price from price information array"""
    return price_info[-1]["value"] if price_info else None

def adjust_prices(price, callout_top_stack):
    """
    Apply the exact pricing logic as specified:
    - For normal products (no callouts): Apply 15% discount to sku_price, subtract 0.01 from current_price for selling_price
    - For promo exclusion: Keep sku_price as current_price, add 0.99 to current_price for selling_price
    - For outlet items: Keep sku_price as current_price, add 1.199 to current_price for selling_price
    """
    # Initialize both prices to current price
    sku_price = price
    selling_price = price
    
    if not callout_top_stack:
        # Normal product - Apply 15% discount to sku_price, subtract 0.01 from current_price
        sku_price = ( price * 0.85 ) + 1
        selling_price = ( price - 0.01 ) + 1
    else:
        # Check for specific callout IDs
        callout_ids = {item.get("id") for item in callout_top_stack}
        if "pdp-promo-nodiscount" in callout_ids:
            # Promo exclusion - Keep sku_price as current_price, add 0.99 to current_price
            sku_price = ( price ) + 1
            selling_price = ( price + 0.99 ) + 1
        elif "pdp-callout-outlet-nopromo" in callout_ids:
            # Outlet item - Keep sku_price as current_price, add 1.199 to current_price
            sku_price = ( price ) + 1
            selling_price = ( price + 1.199 ) + 1
    
    # Round prices to 2 decimal places
    sku_price = float(Decimal(str(sku_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    selling_price = float(Decimal(str(selling_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    return sku_price, selling_price

@app.route('/scrape', methods=['POST'])
def scrape_product():
    """Main scraping endpoint"""
    start_time = time.time()
    
    try:
        # Validate input
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "Missing 'url' parameter"}), 400
            
        product_url = data['url']
        logger.info(f"Processing request for: {product_url}")
        
        # Extract product ID
        product_id = extract_product_id(product_url)
        
        # Configure request parameters
        max_retries = 3
        retry_delay = 2
        api_url = f'https://www.adidas.co.uk/api/product-list/{product_id}'
        
        for attempt in range(max_retries):
            try:
                # Random delay between requests
                time.sleep(random.uniform(0.5, 2.5))
                
                # Get fresh proxy and headers
                proxy = get_random_proxy()
                headers = get_headers(product_url)
                
                # Make request
                response = requests.get(
                    api_url,
                    headers=headers,
                    proxies=proxy,
                    timeout=15,
                    verify=False
                )
                
                # Handle rate limits
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 10))
                    logger.warning(f"Rate limited. Retrying after {retry_after} seconds")
                    time.sleep(retry_after)
                    continue
                    
                response.raise_for_status()
                
                # Process data
                product_data = response.json()[0]
                
                # Extract current price
                current_price = product_data["pricing_information"].get("currentPrice")
                if current_price is None:
                    raise ValueError("Price information is missing from the product data.")
                
                # Get callouts for price adjustment
                callouts = product_data.get("callouts", {})
                callout_top_stack = callouts.get("callout_top_stack", [])
                
                # Apply price adjustments
                sku_price, selling_price = adjust_prices(current_price, callout_top_stack)

                # Extract product description
                product_description = product_data.get("product_description", {}).get("text")
        
                result = {
                    "product_url": str(product_url),
                    "title": str(product_data.get("name", "")),
                    "product_description": product_description,
                    "sku_price": sku_price,
                    "selling_price": selling_price,
                    "currency": "GBP",
                    "product_code": product_id,
                    "colors": [],
                    "sizes": [],
                    "images": {
                        "main_images": [],
                        "color_variants": []
                    }
                }

                # Process main color
                main_color = product_data.get("attribute_list", {}).get("color")
                if main_color:
                    # Get main image with fallback
                    main_image = next(
                        (img["image_url"] for img in product_data.get("view_list", []) 
                         if img.get("type") == "other"),
                        None
                    )
                    # Add fallback to first image if no 'other' type found
                    if not main_image and product_data.get("view_list"):
                        main_image = product_data["view_list"][0]["image_url"]
                    
                    result["colors"].append({
                        "name": main_color,
                        "code": product_id,
                        "image": main_image,
                        "sku_price": sku_price,
                        "selling_price": selling_price
                    })
                    result["images"]["main_images"] = [img["image_url"] 
                                                      for img in product_data.get("view_list", [])]
                
                # Process color variations with price adjustments
                for variation in product_data.get("product_link_list", []):
                    if variation.get("type") == "color-variation" and variation.get("image"):
                        # Get original price for this variant
                        variant_price = get_last_price(variation.get("price_information", []))
                        if variant_price is None:
                            variant_price = current_price  # Fall back to main product price
                        
                        # Apply the same price adjustment logic to color variants
                        variant_sku_price, variant_selling_price = adjust_prices(
                            variant_price, callout_top_stack
                        )
                        
                        result["colors"].append({
                            "name": variation.get("default_color", "Unknown"),
                            "code": variation.get("productId", ""),
                            "image": variation["image"],
                            "sku_price": variant_sku_price,
                            "selling_price": variant_selling_price
                        })
                        result["images"]["color_variants"].append(variation["image"])
                
                # Process sizes
                result["sizes"] = [size.get("size") for size in product_data.get("variation_list", [])]
                
                logger.info(f"Successfully processed in {time.time()-start_time:.2f}s")
                return jsonify(result)
                
            except (requests.exceptions.ProxyError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                logger.warning(f"Proxy error attempt {attempt+1}: {str(e)}")
                time.sleep(retry_delay ** (attempt + 1))
                continue
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    logger.error("Blocked by Adidas anti-bot protection")
                    return jsonify({"error": "Blocked by website security"}), 403
                raise
                
        return jsonify({"error": "All proxy attempts failed"}), 503

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
