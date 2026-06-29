# setup.ps1 - Windows PowerShell setup script
Write-Host "Setting up E-Commerce Web Scraper..." -ForegroundColor Green

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Python is not installed or not in PATH!" -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Install requirements
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "`nTo run the scraper:" -ForegroundColor Cyan
Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "python ecommerce_scraper.py" -ForegroundColor White