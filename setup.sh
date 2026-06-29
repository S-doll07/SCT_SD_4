#!/bin/bash

echo "Setting up E-Commerce Web Scraper..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

echo "Setup complete!"
echo "To run the scraper:"
echo "source venv/bin/activate"
echo "python ecommerce_scraper.py"