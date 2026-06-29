"""
E-Commerce Web Scraper - Fixed Price Extraction
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ECommerceScraper:
    def __init__(self, base_url: str, headers: Optional[Dict] = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session.headers.update(self.headers)
        self.products = []
    
    def fetch_page(self, url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching: {url}")
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
            except requests.RequestException as e:
                logger.error(f"Error fetching {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
        return None
    
    def extract_product_info(self, soup: BeautifulSoup, product_url: str) -> Dict:
        product = {
            'url': product_url,
            'name': 'N/A',
            'price': 'N/A',
            'currency': 'USD',
            'rating': 'N/A',
            'rating_count': 'N/A',
            'availability': 'N/A',
            'description': 'N/A',
            'sku': 'N/A',
            'category': 'N/A',
            'extracted_at': datetime.now().isoformat()
        }
        
        # Name - Try multiple selectors
        name_selectors = ['h1', '.product-title', '.product-name', '.product_main h1']
        for selector in name_selectors:
            name_elem = soup.select_one(selector)
            if name_elem:
                product['name'] = name_elem.text.strip()
                break
        
        # Price - Try multiple selectors for books.toscrape.com
        price_selectors = [
            '.price_color',           # Books to scrape
            '.price',                 # Generic
            '.product-price',         # Generic
            '.current-price',         # Generic
            '.sale-price',            # Generic
            '.price-now',             # Generic
            '.price-box .price',      # Generic
            '.product_main .price_color'  # Books to scrape specific
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.text.strip()
                # Extract numeric price using regex (handles £, $, €, ₹)
                price_match = re.search(r'[\d,]+\.?\d*', price_text)
                if price_match:
                    product['price'] = price_match.group().replace(',', '')
                    # Detect currency
                    if '£' in price_text:
                        product['currency'] = 'GBP'
                    elif '€' in price_text:
                        product['currency'] = 'EUR'
                    elif '$' in price_text:
                        product['currency'] = 'USD'
                    elif '₹' in price_text:
                        product['currency'] = 'INR'
                    else:
                        product['currency'] = 'USD'
                    break
        
        # If price not found, try looking in the whole page for price patterns
        if product['price'] == 'N/A':
            # Search for price pattern in the page
            page_text = soup.get_text()
            price_patterns = [
                r'£([\d,]+\.?\d*)',
                r'\$([\d,]+\.?\d*)',
                r'€([\d,]+\.?\d*)',
                r'₹([\d,]+\.?\d*)'
            ]
            for pattern in price_patterns:
                match = re.search(pattern, page_text)
                if match:
                    product['price'] = match.group(1).replace(',', '')
                    if '£' in pattern:
                        product['currency'] = 'GBP'
                    elif '$' in pattern:
                        product['currency'] = 'USD'
                    elif '€' in pattern:
                        product['currency'] = 'EUR'
                    elif '₹' in pattern:
                        product['currency'] = 'INR'
                    break
        
        # Rating
        rating_elem = soup.select_one('.star-rating')
        if rating_elem:
            rating_classes = rating_elem.get('class', [])
            rating_map = {'One': '1', 'Two': '2', 'Three': '3', 'Four': '4', 'Five': '5'}
            for rc in rating_classes:
                if rc in rating_map:
                    product['rating'] = rating_map[rc]
                    break
        
        # Availability
        avail_elem = soup.select_one('.instock.availability')
        if not avail_elem:
            avail_elem = soup.select_one('.availability')
        if avail_elem:
            product['availability'] = avail_elem.text.strip()
        
        # Description
        desc_elem = soup.select_one('#product_description + p')
        if desc_elem:
            product['description'] = desc_elem.text.strip()[:500]
        
        # SKU (UPC)
        sku_rows = soup.select('.table-striped tr')
        for row in sku_rows:
            th = row.select_one('th')
            td = row.select_one('td')
            if th and td and 'UPC' in th.text:
                product['sku'] = td.text.strip()
                break
        
        # Category
        breadcrumb = soup.select('.breadcrumb li')
        if len(breadcrumb) >= 3:
            product['category'] = breadcrumb[2].text.strip()
        elif len(breadcrumb) == 2:
            product['category'] = breadcrumb[1].text.strip()
        else:
            # Try to extract from URL
            url_parts = product_url.split('/')
            for part in url_parts:
                if part and not part.isdigit() and part not in ['catalogue', 'books', 'index.html']:
                    product['category'] = part.replace('-', ' ').title()
                    break
        
        return product
    
    def scrape_product_listing(self, listing_url: str, max_pages: int = 3) -> List[str]:
        product_urls = []
        
        for page in range(1, max_pages + 1):
            if page == 1:
                page_url = listing_url
            else:
                page_url = listing_url.replace('page-1', f'page-{page}')
            
            soup = self.fetch_page(page_url)
            if not soup:
                break
            
            # Find all book links
            book_links = soup.select('h3 a')
            if not book_links:
                # Try alternative selectors
                book_links = soup.select('.product-item a')
            if not book_links:
                book_links = soup.select('.product a')
            
            for link in book_links:
                href = link.get('href')
                if href:
                    if href.startswith('catalogue/'):
                        full_url = f"{self.base_url}/{href}"
                    elif href.startswith('../'):
                        full_url = urljoin(self.base_url, href.replace('../', 'catalogue/'))
                    else:
                        full_url = urljoin(self.base_url, href)
                    
                    if 'catalogue' not in full_url:
                        full_url = full_url.replace(self.base_url + '/', self.base_url + '/catalogue/')
                    
                    if full_url not in product_urls:
                        product_urls.append(full_url)
            
            logger.info(f"Page {page}: Found {len(book_links)} products, total so far: {len(product_urls)}")
            time.sleep(random.uniform(0.5, 1.0))
        
        return product_urls
    
    def scrape_product_page(self, url: str) -> Optional[Dict]:
        try:
            soup = self.fetch_page(url)
            if not soup:
                return None
            
            product = self.extract_product_info(soup, url)
            
            if product.get('name') != 'N/A' or product.get('price') != 'N/A':
                self.products.append(product)
                logger.info(f"✓ Scraped: {product['name']} - {product['currency']}{product['price']}")
                return product
            else:
                logger.warning(f"Failed to extract meaningful data from {url}")
                return None
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    def scrape_products(self, product_urls: List[str], delay: float = 1.0) -> List[Dict]:
        logger.info(f"Starting to scrape {len(product_urls)} products")
        
        products = []
        for idx, url in enumerate(product_urls, 1):
            logger.info(f"Scraping product {idx}/{len(product_urls)}")
            product = self.scrape_product_page(url)
            
            if product is not None:
                products.append(product)
                logger.info(f"✓ Scraped: {product.get('name', 'N/A')}")
            else:
                logger.warning(f"✗ Failed to scrape product {idx}")
            
            time.sleep(delay + random.uniform(0, 0.5))
        
        logger.info(f"Successfully scraped {len(products)} products")
        return products
    
    def save_to_csv(self, filename: str = None):
        if not self.products:
            logger.warning("No products to save")
            print("❌ No products to save")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'products_{timestamp}.csv'
        
        fields = ['name', 'price', 'currency', 'rating', 'availability', 'sku', 'category', 'description', 'url', 'extracted_at']
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()
                for product in self.products:
                    row = {field: product.get(field, 'N/A') for field in fields}
                    writer.writerow(row)
            
            print(f"✓ Data saved to {filename}")
            logger.info(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
    
    def save_to_json(self, filename: str = None):
        if not self.products:
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'products_{timestamp}.json'
        
        try:
            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(self.products, jsonfile, indent=2, ensure_ascii=False)
            
            print(f"✓ Data saved to {filename}")
            logger.info(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving to JSON: {e}")
    
    def get_statistics(self) -> Dict:
        if not self.products:
            return {'total_products': 0}
        
        stats = {
            'total_products': len(self.products),
            'products_with_price': sum(1 for p in self.products if p['price'] != 'N/A'),
            'products_with_rating': sum(1 for p in self.products if p['rating'] != 'N/A'),
            'average_price': 0.0
        }
        
        prices = []
        for p in self.products:
            try:
                if p['price'] != 'N/A':
                    prices.append(float(p['price']))
            except (ValueError, TypeError):
                pass
        
        if prices:
            stats['average_price'] = sum(prices) / len(prices)
        
        return stats


def main():
    print("\n" + "="*60)
    print("📚 E-COMMERCE BOOK SCRAPER - BOOKS.TOSCRAPE.COM")
    print("="*60 + "\n")
    
    BASE_URL = "https://books.toscrape.com"
    LISTING_URL = "https://books.toscrape.com/catalogue/page-1.html"
    
    print(f"📍 Target: {BASE_URL}")
    print(f"📄 Listing: {LISTING_URL}\n")
    
    scraper = ECommerceScraper(BASE_URL)
    
    try:
        print("📋 Step 1: Collecting product URLs...")
        product_urls = scraper.scrape_product_listing(LISTING_URL, max_pages=3)
        
        if not product_urls:
            print("❌ No product URLs found.")
            return
        
        print(f"✅ Found {len(product_urls)} product URLs\n")
        
        print("📊 Step 2: Scraping product data...")
        products = scraper.scrape_products(product_urls[:10], delay=1.0)
        
        if not products:
            print("❌ No products were scraped.")
            return
        
        print("\n💾 Step 3: Saving data...")
        scraper.save_to_csv()
        scraper.save_to_json()
        
        stats = scraper.get_statistics()
        print("\n📈 Statistics:")
        print("-" * 40)
        print(f"Total Products Scraped: {stats['total_products']}")
        print(f"Products with Prices: {stats['products_with_price']}")
        print(f"Products with Ratings: {stats['products_with_rating']}")
        if stats.get('average_price'):
            print(f"Average Price: ${stats['average_price']:.2f}")
        print("-" * 40)
        
        print("\n🔍 Sample Products (first 5):")
        print("=" * 60)
        for i, product in enumerate(products[:5], 1):
            print(f"\n{i}. 📖 {product['name']}")
            print(f"   💷 Price: {product['currency']}{product['price']}")
            print(f"   ⭐ Rating: {'★' * int(product['rating']) if product['rating'] != 'N/A' else 'No rating'}")
            print(f"   📦 Availability: {product['availability']}")
            if product['category'] != 'N/A':
                print(f"   📂 Category: {product['category']}")
            print("-" * 50)
        
        print(f"\n✅ Scraping completed successfully!")
        print(f"📁 Check the generated files: products_*.csv and products_*.json")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
