"""
E-Commerce Product Scraper - Advanced Version
With Login Page and Unrestricted URL Support
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Global state
scraping_status = {
    'in_progress': False,
    'progress': 0,
    'status': 'Ready',
    'products': [],
    'error': None,
    'logs': []
}

# Session storage
sessions = {}
price_history = {}

def is_valid_url(url):
    """Check if URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

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

@app.route('/api/login', methods=['POST'])
def login():
    """Handle login"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    # Simple authentication - accept any non-empty credentials
    # For production, use proper authentication
    if username and password:
        session['user'] = username
        session['logged_in'] = True
        return jsonify({
            'status': 'success',
            'message': f'Welcome {username}!',
            'redirect': '/'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Please enter username and password'
        }), 400

@app.route('/api/logout', methods=['POST'])
def logout():
    """Handle logout"""
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
                'currency': str(p.get('currency', '£')),
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
                    'price': price
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

@app.route('/api/products')
def get_products():
    global scraping_status
    if not scraping_status['products']:
        json_files = glob.glob('products_*.json')
        if json_files:
            latest_json = sorted(json_files)[-1]
            try:
                with open(latest_json, 'r', encoding='utf-8') as f:
                    products = json.load(f)
                if products and isinstance(products, list):
                    scraping_status['products'] = products
                    return jsonify(products)
            except:
                pass
        
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
                return jsonify(cleaned)
            except:
                pass
    
    return jsonify(scraping_status['products'])

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
    
    for p in products:
        cat = p.get('category', 'Uncategorized')
        categories[cat] = categories.get(cat, 0) + 1
        rating = p.get('rating', 'N/A')
        if rating != 'N/A':
            ratings[rating] = ratings.get(rating, 0) + 1
        try:
            price = float(p.get('price', '0'))
            prices.append(price)
            if price < 10: price_ranges['0-10'] += 1
            elif price < 20: price_ranges['10-20'] += 1
            elif price < 30: price_ranges['20-30'] += 1
            elif price < 40: price_ranges['30-40'] += 1
            elif price < 50: price_ranges['40-50'] += 1
            elif price < 60: price_ranges['50-60'] += 1
            else: price_ranges['60+'] += 1
        except:
            pass
    
    return jsonify({
        'total': len(products),
        'categories': categories,
        'ratings': ratings,
        'price_ranges': price_ranges,
        'avg_price': sum(prices) / len(prices) if prices else 0,
        'min_price': min(prices) if prices else 0,
        'max_price': max(prices) if prices else 0,
        'avg_rating': sum(float(r) for r in ratings.keys()) / len(ratings) if ratings else 0,
        'category_count': len(categories)
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
        
        if chart_type == 'price':
            prices = [float(p.get('price', 0)) for p in products if p.get('price', 'N/A') != 'N/A']
            ax.hist(prices, bins=10, color='#d63384', edgecolor='white', alpha=0.7)
            ax.set_title('Price Distribution', fontsize=14, fontweight='bold')
            ax.set_xlabel('Price (£)')
            ax.set_ylabel('Number of Books')
            ax.grid(True, alpha=0.3)
        elif chart_type == 'rating':
            ratings = [int(p.get('rating', 0)) for p in products if p.get('rating', 'N/A') != 'N/A']
            rating_counts = {i: ratings.count(i) for i in range(1, 6)}
            ax.bar(rating_counts.keys(), rating_counts.values(), color='#6f42c1', edgecolor='white')
            ax.set_title('Rating Distribution', fontsize=14, fontweight='bold')
            ax.set_xlabel('Rating (Stars)')
            ax.set_ylabel('Number of Books')
            ax.set_xticks(range(1, 6))
            ax.grid(True, alpha=0.3)
        elif chart_type == 'category':
            categories = {}
            for p in products:
                cat = p.get('category', 'Uncategorized')
                categories[cat] = categories.get(cat, 0) + 1
            categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10])
            ax.barh(list(categories.keys()), list(categories.values()), color='#d63384')
            ax.set_title('Top Categories', fontsize=14, fontweight='bold')
            ax.set_xlabel('Number of Books')
            ax.grid(True, alpha=0.3)
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

@app.route('/api/export/csv')
def export_csv():
    global scraping_status
    if not scraping_status['products']:
        return jsonify({'error': 'No data to export'}), 400
    
    df = pd.DataFrame(scraping_status['products'])
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

@app.route('/api/export/report')
def export_report():
    global scraping_status
    products = scraping_status['products']
    if not products:
        return jsonify({'error': 'No data'}), 404
    
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
        
        <div class="summary">
            <div class="stat"><div class="value">{len(products)}</div><div class="label">Total Products</div></div>
            <div class="stat"><div class="value">£{sum(float(p.get('price',0)) for p in products if p.get('price','N/A')!='N/A')/len(products) if products else 0:.2f}</div><div class="label">Avg Price</div></div>
            <div class="stat"><div class="value">{sum(int(p.get('rating',0)) for p in products if p.get('rating','N/A')!='N/A')/len(products) if products else 0:.1f}</div><div class="label">Avg Rating</div></div>
            <div class="stat"><div class="value">{len(set(p.get('category','Uncategorized') for p in products))}</div><div class="label">Categories</div></div>
        </div>
        
        <table>
            <thead><tr><th>Name</th><th>Price</th><th>Rating</th><th>Category</th></tr></thead>
            <tbody>
                {''.join(f'<tr><td>{p.get("name","N/A")}</td><td>{p.get("currency","£")}{p.get("price","N/A")}</td><td>{"★"*int(p.get("rating",0))}{"☆"*(5-int(p.get("rating",0)))}</td><td>{p.get("category","Uncategorized")}</td></tr>' for p in products[:50])}
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
    
    load_existing_data()
    
    print("\n🚀 Starting server on http://127.0.0.1:5000")
    print("🌐 Any valid URL can be scraped")
    print("📱 Features: Login, Wishlist, Compare, Quick Stats, Auto-Tags")
    print("⏹️ Press Ctrl+C to stop")
    print("="*60 + "\n")
    app.run(debug=True, port=5000)