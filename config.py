"""
Configuration file for the e-commerce scraper
"""

# Website configuration
WEBSITE_CONFIG = {
    'base_url': 'https://www.example-ecommerce.com',
    'listing_url': 'https://www.example-ecommerce.com/products',
    'max_pages': 5,
    'max_products': 50,
    'request_delay': 1.5,  # seconds between requests
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Selectors for product information
SELECTORS = {
    'product_name': ['h1.product-title', '.product-name', 'h1'],
    'price': ['.price', '.product-price', '.current-price'],
    'rating': ['.rating', '.star-rating', '.product-rating'],
    'availability': ['.availability', '.stock-status'],
    'description': ['.product-description', '.description'],
    'sku': ['.sku', '.product-sku']
}

# Output settings
OUTPUT_CONFIG = {
    'csv_filename': 'products.csv',
    'json_filename': 'products.json',
    'encoding': 'utf-8'
}