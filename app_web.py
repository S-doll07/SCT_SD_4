"""
E-Commerce Product Scraper - Advanced Version
With Multi-Currency Support (INR, USD, EUR, GBP)
"""

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import pandas as pd
import json
import os
import glob
from datetime import datetime
import threading
import logging
import traceback
import requests
from urllib.parse import urlparse
import io
import secrets
import hashlib
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# ========================================
# CURRENCY CONFIGURATION - REAL EXCHANGE RATES
# ========================================
CURRENCIES = {
    'INR': {
        'symbol': '₹',
        'name': 'Indian Rupee',
        'rate': 1.0,  # Base currency
        'flag': '🇮🇳'
    },
    'USD': {
        'symbol': '$',
        'name': 'US Dollar',
        'rate': 0.012,  # 1 INR = 0.012 USD
        'flag': '🇺🇸'
    },
    'EUR': {
        'symbol': '€',
        'name': 'Euro',
        'rate': 0.011,  # 1 INR = 0.011 EUR
        'flag': '🇪🇺'
    },
    'GBP': {
        'symbol': '£',
        'name': 'British Pound',
        'rate': 0.0095,  # 1 INR = 0.0095 GBP
        'flag': '🇬🇧'
    }
}

DEFAULT_CURRENCY = 'INR'

# ========================================
# USER DATABASE
# ========================================
USERS_FILE = 'users.json'

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    """Save users to JSON file"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except:
        return False

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Password is strong"

def convert_currency(amount, from_currency, to_currency):
    """Convert amount from one currency to another using INR as base"""
    if amount == 'N/A' or amount == '' or amount is None:
        return 'N/A'
    try:
        amount = float(amount)
        
        # If currencies are the same, return original
        if from_currency == to_currency:
            return amount
        
        # Convert to INR first (base currency)
        if from_currency != 'INR' and from_currency in CURRENCIES:
            # Convert from source to INR
            amount = amount / CURRENCIES[from_currency]['rate']
        elif from_currency not in CURRENCIES:
            # If currency not in our list, assume it's already in INR
            pass
        
        # Convert from INR to target
        if to_currency != 'INR' and to_currency in CURRENCIES:
            amount = amount * CURRENCIES[to_currency]['rate']
        
        return round(amount, 2)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Currency conversion error: {e}")
        return 'N/A'

def get_currency_symbol(currency_code):
    """Get currency symbol"""
    return CURRENCIES.get(currency_code, {}).get('symbol', '₹')

# ========================================
# GLOBAL STATE
# ========================================
scraping_status = {
    'in_progress': False,
    'progress': 0,
    'status': 'Ready',
    'products': [],
    'error': None,
    'logs': []
}

sessions = {}
price_history = {}
current_currency = DEFAULT_CURRENCY

# ========================================
# ROUTES
# ========================================
@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login')
def login_page():
    """Login page"""
    if session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    """Register page"""
    if session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('register.html')

# ========================================
# AUTH API ENDPOINTS
# ========================================
@app.route('/api/register', methods=['POST'])
def register():
    """Handle user registration"""
    data = request.json
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    
    if not username or not email or not password:
        return jsonify({
            'status': 'error',
            'message': 'All fields are required'
        }), 400
    
    if password != confirm_password:
        return jsonify({
            'status': 'error',
            'message': 'Passwords do not match'
        }), 400
    
    if not validate_email(email):
        return jsonify({
            'status': 'error',
            'message': 'Invalid email format'
        }), 400
    
    is_valid, msg = validate_password(password)
    if not is_valid:
        return jsonify({
            'status': 'error',
            'message': msg
        }), 400
    
    users = load_users()
    
    if username in users:
        return jsonify({
            'status': 'error',
            'message': 'Username already exists'
        }), 400
    
    for user_data in users.values():
        if user_data.get('email') == email:
            return jsonify({
                'status': 'error',
                'message': 'Email already registered'
            }), 400
    
    users[username] = {
        'username': username,
        'email': email,
        'password': hash_password(password),
        'created_at': datetime.now().isoformat(),
        'last_login': None,
        'currency': DEFAULT_CURRENCY,
        'data': {
            'products': [],
            'wishlist': [],
            'sessions': {},
            'settings': {
                'theme': 'default',
                'dark_mode': False,
                'currency': DEFAULT_CURRENCY
            }
        }
    }
    
    if save_users(users):
        return jsonify({
            'status': 'success',
            'message': 'Registration successful! Please login.',
            'redirect': '/login'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Failed to save user data'
        }), 500

@app.route('/api/login', methods=['POST'])
def login():
    """Handle user login"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({
            'status': 'error',
            'message': 'Please enter username and password'
        }), 400
    
    users = load_users()
    
    if username not in users:
        return jsonify({
            'status': 'error',
            'message': 'Invalid username or password'
        }), 400
    
    if users[username]['password'] != hash_password(password):
        return jsonify({
            'status': 'error',
            'message': 'Invalid username or password'
        }), 400
    
    users[username]['last_login'] = datetime.now().isoformat()
    save_users(users)
    
    session['user'] = username
    session['logged_in'] = True
    session['currency'] = users[username].get('currency', DEFAULT_CURRENCY)
    
    load_user_data(username)
    
    return jsonify({
        'status': 'success',
        'message': f'Welcome back {username}!',
        'redirect': '/'
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    """Handle logout"""
    username = session.get('user')
    if username:
        save_user_data(username)
    session.clear()
    return jsonify({'status': 'success', 'message': 'Logged out successfully'})

@app.route('/api/check_auth')
def check_auth():
    """Check if user is logged in"""
    if session.get('logged_in'):
        return jsonify({
            'logged_in': True,
            'user': session.get('user', 'Guest')
        })
    return jsonify({'logged_in': False})

@app.route('/api/user/profile')
def user_profile():
    """Get user profile"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    users = load_users()
    username = session.get('user')
    
    if username in users:
        user_data = users[username].copy()
        user_data.pop('password', None)
        return jsonify(user_data)
    
    return jsonify({'error': 'User not found'}), 404

# ========================================
# CURRENCY API ENDPOINTS
# ========================================
@app.route('/api/currencies')
def get_currencies():
    """Get list of supported currencies"""
    return jsonify(CURRENCIES)

@app.route('/api/currency/set', methods=['POST'])
def set_currency():
    """Set user's preferred currency"""
    global current_currency
    
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    currency = data.get('currency', DEFAULT_CURRENCY)
    
    if currency not in CURRENCIES:
        return jsonify({'error': 'Invalid currency'}), 400
    
    current_currency = currency
    session['currency'] = currency
    
    # Save to user profile
    users = load_users()
    username = session.get('user')
    if username in users:
        users[username]['currency'] = currency
        if 'data' in users[username] and 'settings' in users[username]['data']:
            users[username]['data']['settings']['currency'] = currency
        save_users(users)
    
    return jsonify({
        'status': 'success',
        'currency': currency,
        'symbol': get_currency_symbol(currency)
    })

@app.route('/api/currency/current')
def get_current_currency():
    """Get current currency"""
    return jsonify({
        'currency': session.get('currency', DEFAULT_CURRENCY),
        'symbol': get_currency_symbol(session.get('currency', DEFAULT_CURRENCY))
    })

# ========================================
# USER DATA MANAGEMENT
# ========================================
def load_user_data(username):
    """Load user's data into session"""
    users = load_users()
    if username in users:
        user_data = users[username].get('data', {})
        scraping_status['products'] = user_data.get('products', [])
        session['currency'] = users[username].get('currency', DEFAULT_CURRENCY)

def save_user_data(username):
    """Save current session data to user's profile"""
    users = load_users()
    if username in users:
        if 'data' not in users[username]:
            users[username]['data'] = {}
        users[username]['data']['products'] = scraping_status['products']
        users[username]['data']['settings']['currency'] = session.get('currency', DEFAULT_CURRENCY)
        save_users(users)

def is_valid_url(url):
    """Check if URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

# ========================================
# SCRAPING ROUTES
# ========================================
@app.route('/api/scrape', methods=['POST'])
def scrape():
    global scraping_status
    
    if not session.get('logged_in'):
        return jsonify({'error': 'Please login first'}), 401
    
    if scraping_status['in_progress']:
        return jsonify({'error': 'Scraping already in progress'}), 400
    
    data = request.json
    url = data.get('url', 'https://books.toscrape.com/catalogue/page-1.html')
    
    if not is_valid_url(url):
        return jsonify({'error': 'Invalid URL format'}), 400
    
    max_pages = int(data.get('max_pages', 3))
    max_products = int(data.get('max_products', 25))
    
    scraping_status = {
        'in_progress': True,
        'progress': 0,
        'status': 'Initializing...',
        'products': [],
        'error': None,
        'logs': ['🚀 Starting scraper...']
    }
    
    thread = threading.Thread(target=run_scraper, args=(url, max_pages, max_products))
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': 'Scraping started'})

def add_log(message):
    global scraping_status
    timestamp = datetime.now().strftime('%H:%M:%S')
    scraping_status['logs'].append(f'[{timestamp}] {message}')
    if len(scraping_status['logs']) > 100:
        scraping_status['logs'] = scraping_status['logs'][-100:]

def run_scraper(url, max_pages, max_products):
    global scraping_status, price_history
    
    try:
        add_log('📚 Initializing scraper...')
        scraping_status['progress'] = 10
        scraping_status['status'] = 'Initializing scraper...'
        
        from ecommerce_scraper import ECommerceScraper
        
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        add_log(f'🌐 Base URL: {base_url}')
        
        scraper = ECommerceScraper(base_url)
        
        add_log('🔗 Collecting product URLs...')
        scraping_status['progress'] = 20
        scraping_status['status'] = 'Collecting product URLs...'
        
        product_urls = scraper.scrape_product_listing(url, max_pages=max_pages)
        add_log(f'✅ Found {len(product_urls)} product URLs')
        
        if not product_urls:
            scraping_status['status'] = 'No products found!'
            scraping_status['in_progress'] = False
            add_log('❌ No products found!')
            return
        
        scraping_status['progress'] = 40
        scraping_status['status'] = f'Found {len(product_urls)} products. Scraping data...'
        add_log(f'📊 Scraping {min(max_products, len(product_urls))} products...')
        
        products_to_scrape = min(max_products, len(product_urls))
        raw_products = scraper.scrape_products(product_urls[:products_to_scrape], delay=0.3)
        
        products = []
        for p in raw_products:
            if p is None or not isinstance(p, dict):
                continue
            if p.get('name') == 'N/A' and p.get('price') == 'N/A':
                continue
            
            clean_product = {
                'name': str(p.get('name', 'N/A')),
                'price': str(p.get('price', 'N/A')),
                'currency': str(p.get('currency', 'GBP')),  # Books to scrape uses GBP
                'rating': str(p.get('rating', 'N/A')),
                'rating_count': str(p.get('rating_count', 'N/A')),
                'availability': str(p.get('availability', 'N/A')),
                'category': str(p.get('category', 'Uncategorized')),
                'url': str(p.get('url', '')),
                'extracted_at': datetime.now().isoformat(),
                'tags': [],
                'notes': ''
            }
            products.append(clean_product)
        
        add_log(f'✅ Cleaned {len(products)} valid products')
        
        if not products:
            scraping_status['status'] = 'No valid products found!'
            scraping_status['in_progress'] = False
            add_log('❌ No valid products found!')
            return
        
        timestamp = datetime.now().isoformat()
        for product in products:
            name = product['name']
            if name not in price_history:
                price_history[name] = []
            try:
                price = float(product['price']) if product['price'] != 'N/A' else 0
                price_history[name].append({
                    'timestamp': timestamp,
                    'price': price,
                    'currency': product.get('currency', 'GBP')
                })
            except:
                pass
            if len(price_history[name]) > 30:
                price_history[name] = price_history[name][-30:]
        
        scraping_status['progress'] = 80
        scraping_status['status'] = f'Saving {len(products)} products...'
        add_log(f'💾 Saving {len(products)} products...')
        
        scraper.products = products
        scraper.save_to_csv()
        scraper.save_to_json()
        
        scraping_status['products'] = products
        scraping_status['progress'] = 100
        scraping_status['status'] = f'✅ Complete! Found {len(products)} products.'
        add_log(f'✅ Scraping complete! {len(products)} products saved.')
        
        username = session.get('user')
        if username:
            save_user_data(username)
        
        try:
            with open('price_history.json', 'w') as f:
                json.dump(price_history, f)
        except:
            pass
        
    except Exception as e:
        error_msg = f'Error: {str(e)}'
        logger.error(f"Scraping error: {e}")
        logger.error(traceback.format_exc())
        scraping_status['status'] = f'❌ {error_msg}'
        scraping_status['error'] = error_msg
        add_log(f'❌ {error_msg}')
    finally:
        scraping_status['in_progress'] = False
        add_log('🏁 Scraping finished')

# ========================================
# PRODUCT ROUTES WITH FIXED PRICE DISPLAY
# ========================================
@app.route('/api/products')
def get_products():
    global scraping_status
    
    # If no products in memory, load from files
    if not scraping_status['products']:
        json_files = glob.glob('products_*.json')
        if json_files:
            latest_json = sorted(json_files)[-1]
            try:
                with open(latest_json, 'r', encoding='utf-8') as f:
                    products = json.load(f)
                if products and isinstance(products, list):
                    scraping_status['products'] = products
                    logger.info(f"Loaded {len(products)} products from JSON")
            except Exception as e:
                logger.error(f"Error loading JSON: {e}")
        
        csv_files = glob.glob('products_*.csv')
        if csv_files and not scraping_status['products']:
            latest_csv = sorted(csv_files)[-1]
            try:
                df = pd.read_csv(latest_csv)
                products = df.to_dict('records')
                cleaned = []
                for p in products:
                    if p and isinstance(p, dict):
                        clean = {
                            'name': str(p.get('name', 'N/A')),
                            'price': str(p.get('price', 'N/A')),
                            'currency': str(p.get('currency', 'GBP')),
                            'rating': str(p.get('rating', 'N/A')),
                            'rating_count': str(p.get('rating_count', 'N/A')),
                            'availability': str(p.get('availability', 'N/A')),
                            'category': str(p.get('category', 'Uncategorized')),
                            'url': str(p.get('url', '')),
                            'extracted_at': str(p.get('extracted_at', datetime.now().isoformat()))
                        }
                        cleaned.append(clean)
                scraping_status['products'] = cleaned
                logger.info(f"Loaded {len(cleaned)} products from CSV")
            except Exception as e:
                logger.error(f"Error loading CSV: {e}")
    
    # If still no products, return empty list
    if not scraping_status['products']:
        return jsonify([])
    
    # Convert prices to current currency
    target_currency = session.get('currency', DEFAULT_CURRENCY)
    converted_products = []
    
    for product in scraping_status['products']:
        converted = product.copy()
        
        # Get price and currency
        price_str = product.get('price', 'N/A')
        source_currency = product.get('currency', 'GBP')
        
        # Handle N/A or empty price
        if price_str == 'N/A' or price_str == '' or price_str is None:
            converted['price'] = 'N/A'
            converted['currency'] = target_currency
            converted['display_price'] = 'N/A'
            converted['original_price'] = 'N/A'
            converted['original_currency'] = source_currency
        else:
            try:
                # Clean price string
                clean_price = str(price_str).replace(',', '').strip()
                price_value = float(clean_price)
                
                # Store original price and currency
                converted['original_price'] = price_value
                converted['original_currency'] = source_currency
                
                # Convert if needed
                if source_currency != target_currency:
                    converted_price = convert_currency(price_value, source_currency, target_currency)
                    if converted_price == 'N/A':
                        converted_price = price_value
                        converted['currency'] = source_currency
                    else:
                        converted['currency'] = target_currency
                else:
                    converted_price = price_value
                    converted['currency'] = target_currency
                
                # Store as string
                converted['price'] = str(converted_price)
                converted['display_price'] = f"{get_currency_symbol(converted['currency'])}{converted_price:.2f}"
            except (ValueError, TypeError) as e:
                logger.warning(f"Price conversion failed for {product.get('name', 'Unknown')}: {e}")
                converted['price'] = price_str
                converted['currency'] = source_currency
                converted['display_price'] = f"{get_currency_symbol(source_currency)}{price_str}"
                converted['original_price'] = price_str
                converted['original_currency'] = source_currency
        
        converted_products.append(converted)
    
    return jsonify(converted_products)

# ========================================
# EXISTING ROUTES
# ========================================

@app.route('/api/status')
def get_status():
    global scraping_status
    return jsonify({
        'in_progress': scraping_status['in_progress'],
        'progress': scraping_status['progress'],
        'status': scraping_status['status'],
        'product_count': len(scraping_status['products']),
        'error': scraping_status.get('error'),
        'logs': scraping_status.get('logs', [])
    })

@app.route('/api/products/stats')
def get_stats():
    global scraping_status
    products = scraping_status['products']
    if not products:
        return jsonify({'error': 'No products'}), 404
    
    categories = {}
    ratings = {}
    price_ranges = {'0-10': 0, '10-20': 0, '20-30': 0, '30-40': 0, '40-50': 0, '50-60': 0, '60+': 0}
    prices = []
    target_currency = session.get('currency', DEFAULT_CURRENCY)
    
    for p in products:
        cat = p.get('category', 'Uncategorized')
        categories[cat] = categories.get(cat, 0) + 1
        rating = p.get('rating', 'N/A')
        if rating != 'N/A':
            ratings[rating] = ratings.get(rating, 0) + 1
        try:
            price_str = p.get('price', '0')
            if price_str != 'N/A' and price_str != '':
                price = float(str(price_str).replace(',', ''))
                if p.get('currency') and p.get('currency') != target_currency:
                    price = convert_currency(price, p.get('currency', 'GBP'), target_currency)
                if isinstance(price, (int, float)):
                    prices.append(price)
                    if price < 10: price_ranges['0-10'] += 1
                    elif price < 20: price_ranges['10-20'] += 1
                    elif price < 30: price_ranges['20-30'] += 1
                    elif price < 40: price_ranges['30-40'] += 1
                    elif price < 50: price_ranges['40-50'] += 1
                    elif price < 60: price_ranges['50-60'] += 1
                    else: price_ranges['60+'] += 1
        except (ValueError, TypeError):
            pass
    
    avg_price = sum(prices) / len(prices) if prices else 0
    
    return jsonify({
        'total': len(products),
        'categories': categories,
        'ratings': ratings,
        'price_ranges': price_ranges,
        'avg_price': avg_price,
        'min_price': min(prices) if prices else 0,
        'max_price': max(prices) if prices else 0,
        'avg_rating': sum(float(r) for r in ratings.keys()) / len(ratings) if ratings else 0,
        'category_count': len(categories),
        'currency': target_currency,
        'currency_symbol': get_currency_symbol(target_currency)
    })

@app.route('/api/export/chart/<chart_type>')
def export_chart(chart_type):
    global scraping_status
    products = scraping_status['products']
    if not products:
        return jsonify({'error': 'No data'}), 404
    
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 6))
        plt.style.use('seaborn-v0_8')
        
        target_currency = session.get('currency', DEFAULT_CURRENCY)
        currency_symbol = get_currency_symbol(target_currency)
        
        if chart_type == 'price':
            prices = []
            for p in products:
                if p.get('price', 'N/A') != 'N/A' and p.get('price', '') != '':
                    try:
                        price = float(str(p['price']).replace(',', ''))
                        if p.get('currency') and p.get('currency') != target_currency:
                            price = convert_currency(price, p.get('currency', 'GBP'), target_currency)
                        if isinstance(price, (int, float)):
                            prices.append(price)
                    except (ValueError, TypeError):
                        pass
            if prices:
                ax.hist(prices, bins=10, color='#d63384', edgecolor='white', alpha=0.7)
                ax.set_title(f'Price Distribution ({currency_symbol})', fontsize=14, fontweight='bold')
                ax.set_xlabel(f'Price ({currency_symbol})')
                ax.set_ylabel('Number of Books')
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, 'No price data available', ha='center', va='center', transform=ax.transAxes)
        elif chart_type == 'rating':
            ratings = []
            for p in products:
                if p.get('rating', 'N/A') != 'N/A':
                    try:
                        ratings.append(int(p['rating']))
                    except (ValueError, TypeError):
                        pass
            if ratings:
                rating_counts = {i: ratings.count(i) for i in range(1, 6)}
                ax.bar(rating_counts.keys(), rating_counts.values(), color='#6f42c1', edgecolor='white')
                ax.set_title('Rating Distribution', fontsize=14, fontweight='bold')
                ax.set_xlabel('Rating (Stars)')
                ax.set_ylabel('Number of Books')
                ax.set_xticks(range(1, 6))
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, 'No rating data available', ha='center', va='center', transform=ax.transAxes)
        elif chart_type == 'category':
            categories = {}
            for p in products:
                cat = p.get('category', 'Uncategorized')
                categories[cat] = categories.get(cat, 0) + 1
            categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10])
            if categories:
                ax.barh(list(categories.keys()), list(categories.values()), color='#d63384')
                ax.set_title('Top Categories', fontsize=14, fontweight='bold')
                ax.set_xlabel('Number of Books')
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, 'No category data available', ha='center', va='center', transform=ax.transAxes)
        else:
            return jsonify({'error': 'Invalid chart type'}), 400
        
        plt.tight_layout()
        img = io.BytesIO()
        plt.savefig(img, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        img.seek(0)
        
        return send_file(img, mimetype='image/png', 
                        download_name=f'{chart_type}_chart_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
    except ImportError:
        return jsonify({'error': 'Matplotlib not installed'}), 500
    except Exception as e:
        return jsonify({'error': f'Chart export failed: {str(e)}'}), 500

@app.route('/api/export/csv')
def export_csv():
    global scraping_status
    if not scraping_status['products']:
        return jsonify({'error': 'No data to export'}), 400
    
    df = pd.DataFrame(scraping_status['products'])
    target_currency = session.get('currency', DEFAULT_CURRENCY)
    
    # Add display columns
    df['display_currency'] = target_currency
    df['display_currency_symbol'] = get_currency_symbol(target_currency)
    
    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False)
    return send_file(filename, as_attachment=True)

@app.route('/api/export/json')
def export_json():
    global scraping_status
    if not scraping_status['products']:
        return jsonify({'error': 'No data to export'}), 400
    
    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(scraping_status['products'], f, indent=2)
    return send_file(filename, as_attachment=True)

@app.route('/api/export/excel')
def export_excel():
    global scraping_status
    if not scraping_status['products']:
        return jsonify({'error': 'No data to export'}), 400
    
    try:
        import openpyxl
        df = pd.DataFrame(scraping_status['products'])
        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(filename, index=False)
        return send_file(filename, as_attachment=True)
    except ImportError:
        return jsonify({'error': 'Excel export requires openpyxl'}), 500

@app.route('/api/export/qr')
def generate_qr():
    """Generate QR code for sharing data"""
    global scraping_status
    if not scraping_status['products']:
        return jsonify({'error': 'No data to generate QR code'}), 404
    
    try:
        import qrcode
        from io import BytesIO
        
        data = {
            'total': len(scraping_status['products']),
            'timestamp': datetime.now().isoformat(),
            'categories': len(set(p.get('category', 'Uncategorized') for p in scraping_status['products'])),
            'currency': session.get('currency', DEFAULT_CURRENCY)
        }
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(data))
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="#d63384", back_color="white")
        
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png', 
                        download_name=f'qr_code_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
    except ImportError:
        return jsonify({'error': 'QR code module not installed. Run: pip install qrcode pillow'}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to generate QR: {str(e)}'}), 500

@app.route('/api/export/report')
def export_report():
    global scraping_status
    products = scraping_status['products']
    if not products:
        return jsonify({'error': 'No data'}), 404
    
    target_currency = session.get('currency', DEFAULT_CURRENCY)
    currency_symbol = get_currency_symbol(target_currency)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Product Report</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; padding: 40px; background: #fff5f7; }}
            h1 {{ color: #d63384; border-bottom: 3px solid #d63384; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background: #d63384; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 8px 10px; border-bottom: 1px solid #f0d0d8; }}
            tr:nth-child(even) {{ background: #fff0f3; }}
            .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
            .stat {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(214,51,132,0.1); }}
            .stat .value {{ font-size: 24px; font-weight: bold; color: #d63384; }}
            .stat .label {{ font-size: 12px; color: #6c4a6d; }}
            .footer {{ margin-top: 30px; color: #999; font-size: 12px; text-align: center; }}
        </style>
    </head>
    <body>
        <h1>📊 Product Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Currency: {target_currency} ({currency_symbol})</p>
        
        <div class="summary">
            <div class="stat"><div class="value">{len(products)}</div><div class="label">Total Products</div></div>
            <div class="stat"><div class="value">{currency_symbol}{sum(float(p.get('price',0)) for p in products if p.get('price','N/A')!='N/A')/len(products) if products else 0:.2f}</div><div class="label">Avg Price</div></div>
            <div class="stat"><div class="value">{sum(int(p.get('rating',0)) for p in products if p.get('rating','N/A')!='N/A')/len(products) if products else 0:.1f}</div><div class="label">Avg Rating</div></div>
            <div class="stat"><div class="value">{len(set(p.get('category','Uncategorized') for p in products))}</div><div class="label">Categories</div></div>
        </div>
        
        <table>
            <thead><tr><th>Name</th><th>Price ({currency_symbol})</th><th>Rating</th><th>Category</th></tr></thead>
            <tbody>
                {''.join(f'<tr><td>{p.get("name","N/A")}</td><td>{currency_symbol}{p.get("price","N/A")}</td><td>{"★"*int(p.get("rating",0))}{"☆"*(5-int(p.get("rating",0)))}</td><td>{p.get("category","Uncategorized")}</td></tr>' for p in products[:50])}
                {'' if len(products) <= 50 else f'<tr><td colspan="4" style="text-align:center;">... and {len(products)-50} more products</td></tr>'}
            </tbody>
        </table>
        
        <div class="footer">Generated by Product Scraper Pro v4.0</div>
    </body>
    </html>
    """
    return html

@app.route('/api/sessions', methods=['GET', 'POST'])
def handle_sessions():
    global sessions
    if request.method == 'POST':
        data = request.json
        session_name = data.get('name', f'session_{len(sessions)+1}')
        sessions[session_name] = {
            'products': scraping_status['products'].copy(),
            'created': datetime.now().isoformat(),
            'count': len(scraping_status['products'])
        }
        return jsonify({'status': 'success', 'session': session_name})
    else:
        return jsonify(sessions)

@app.route('/api/sessions/load/<session_name>')
def load_session(session_name):
    global sessions, scraping_status
    if session_name not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    scraping_status['products'] = sessions[session_name]['products']
    return jsonify({'status': 'success', 'count': len(scraping_status['products'])})

@app.route('/api/sessions/delete/<session_name>')
def delete_session(session_name):
    global sessions
    if session_name in sessions:
        del sessions[session_name]
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Session not found'}), 404

@app.route('/api/price_history/<product_name>')
def get_price_history(product_name):
    global price_history
    if product_name not in price_history:
        return jsonify([])
    return jsonify(price_history[product_name])

@app.route('/api/tags', methods=['POST'])
def add_tags():
    global scraping_status
    data = request.json
    product_name = data.get('name')
    tags = data.get('tags', [])
    
    for product in scraping_status['products']:
        if product.get('name') == product_name:
            if 'tags' not in product:
                product['tags'] = []
            product['tags'] = list(set(product['tags'] + tags))
            return jsonify({'status': 'success', 'tags': product['tags']})
    
    return jsonify({'error': 'Product not found'}), 404

@app.route('/api/load_json')
def load_json():
    global scraping_status
    json_files = glob.glob('products_*.json')
    if json_files:
        latest_json = sorted(json_files)[-1]
        try:
            with open(latest_json, 'r', encoding='utf-8') as f:
                products = json.load(f)
            if products and isinstance(products, list):
                scraping_status['products'] = products
                return jsonify({'status': 'success', 'count': len(products), 'file': latest_json})
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)})
    return jsonify({'status': 'error', 'error': 'No JSON files found'})

@app.route('/api/load_csv')
def load_csv():
    global scraping_status
    csv_files = glob.glob('products_*.csv')
    if csv_files:
        latest_csv = sorted(csv_files)[-1]
        try:
            df = pd.read_csv(latest_csv)
            products = df.to_dict('records')
            cleaned = []
            for p in products:
                if p and isinstance(p, dict):
                    clean = {k: str(v) if v is not None else 'N/A' for k, v in p.items()}
                    cleaned.append(clean)
            scraping_status['products'] = cleaned
            return jsonify({'status': 'success', 'count': len(cleaned), 'file': latest_csv})
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)})
    return jsonify({'status': 'error', 'error': 'No CSV files found'})

@app.route('/api/test')
def test():
    return jsonify({'status': 'ok', 'message': 'Server is running!'})

@app.route('/api/debug')
def debug():
    global scraping_status
    return jsonify({
        'in_progress': scraping_status['in_progress'],
        'products_count': len(scraping_status['products']),
        'status': scraping_status['status'],
        'error': scraping_status.get('error'),
        'logs': scraping_status.get('logs', [])[-10:],
        'sessions': list(sessions.keys()),
        'price_history_count': len(price_history)
    })

@app.route('/api/files')
def list_files():
    files = {
        'json': glob.glob('products_*.json'),
        'csv': glob.glob('products_*.csv'),
        'excel': glob.glob('products_*.xlsx')
    }
    return jsonify(files)

def load_existing_data():
    global scraping_status, price_history
    json_files = glob.glob('products_*.json')
    if json_files:
        latest_json = sorted(json_files)[-1]
        try:
            with open(latest_json, 'r', encoding='utf-8') as f:
                products = json.load(f)
            if products and isinstance(products, list):
                scraping_status['products'] = products
                print(f"✅ Auto-loaded {len(products)} products from {latest_json}")
        except Exception as e:
            print(f"❌ Error loading JSON: {e}")
    
    try:
        with open('price_history.json', 'r') as f:
            price_history = json.load(f)
        print(f"✅ Loaded price history for {len(price_history)} products")
    except:
        pass

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🕸️ Web Scraper Pro - Advanced v4.0")
    print("="*60)
    print(f"💰 Supported Currencies: INR (₹), USD ($), EUR (€), GBP (£)")
    print("="*60)
    
    load_existing_data()
    
    print("\n🚀 Starting server on http://127.0.0.1:5000")
    print("🔐 Registration and Login System Active")
    print("💱 Multi-Currency Support Available (INR as base)")
    print("⏹️ Press Ctrl+C to stop")
    print("="*60 + "\n")
    app.run(debug=True, port=5000)
