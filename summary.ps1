# summary_simple.ps1 - Simple data summary
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PRODUCT DATA SUMMARY" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

# Find the latest CSV
$csv = Get-ChildItem -Filter "products_*.csv" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($csv) {
    $data = Import-Csv $csv.Name
    
    Write-Host ""
    Write-Host "File: $($csv.Name)" -ForegroundColor Green
    Write-Host "Total Products: $($data.Count)" -ForegroundColor White
    
    # Calculate average price
    $prices = $data | ForEach-Object { [double]$_.price }
    $avgPrice = ($prices | Measure-Object -Average).Average
    Write-Host "Average Price: $([math]::Round($avgPrice, 2))" -ForegroundColor White
    
    # Find min and max prices
    $minPrice = $data | Sort-Object {[double]$_.price} | Select-Object -First 1
    $maxPrice = $data | Sort-Object {[double]$_.price} -Descending | Select-Object -First 1
    Write-Host "Cheapest: $($minPrice.name) - $($minPrice.price)" -ForegroundColor Green
    Write-Host "Most Expensive: $($maxPrice.name) - $($maxPrice.price)" -ForegroundColor Green
    
    # Categories
    Write-Host ""
    Write-Host "Categories:" -ForegroundColor Yellow
    $categories = $data | Group-Object category | Sort-Object Count -Descending
    foreach ($cat in $categories) {
        Write-Host "  $($cat.Name): $($cat.Count) books" -ForegroundColor White
    }
    
    # Ratings
    Write-Host ""
    Write-Host "Ratings:" -ForegroundColor Yellow
    $ratings = $data | Group-Object rating | Sort-Object Name
    foreach ($r in $ratings) {
        Write-Host "  $($r.Name) stars: $($r.Count) books" -ForegroundColor White
    }
    
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
} else {
    Write-Host "No CSV files found. Run the scraper first!" -ForegroundColor Red
}