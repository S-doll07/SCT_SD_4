"""
Price Analysis - Find deals and patterns
"""

import pandas as pd
import glob

csv_files = glob.glob('products_*.csv')
if not csv_files:
    print("No CSV files found!")
    exit()

latest_csv = sorted(csv_files)[-1]
df = pd.read_csv(latest_csv)
df['price'] = df['price'].astype(float)
df['rating'] = df['rating'].astype(int)

print("="*60)
print("💰 PRICE ANALYSIS")
print("="*60)

# Price statistics
print(f"\n📊 Price Statistics:")
print(f"  • Mean: £{df['price'].mean():.2f}")
print(f"  • Median: £{df['price'].median():.2f}")
print(f"  • Min: £{df['price'].min():.2f}")
print(f"  • Max: £{df['price'].max():.2f}")
print(f"  • Range: £{df['price'].max() - df['price'].min():.2f}")

# Price segments
print("\n📊 Price Segments:")
segments = [
    (0, 20, "Budget (£0-20)"),
    (20, 35, "Mid-Range (£20-35)"),
    (35, 50, "Premium (£35-50)"),
    (50, 100, "Luxury (£50+)")
]

for min_price, max_price, label in segments:
    count = df[(df['price'] >= min_price) & (df['price'] < max_price)].shape[0]
    avg_rating = df[(df['price'] >= min_price) & (df['price'] < max_price)]['rating'].mean()
    print(f"  • {label}: {count} books (Avg Rating: {avg_rating:.1f}⭐)")

# Best value books (high rating, low price)
print("\n🏆 Best Value Books (High Rating + Low Price):")
df['value_score'] = df['rating'] / (df['price'] / 10)  # Simple value metric
best_value = df.nlargest(5, 'value_score')[['name', 'price', 'rating']]
for idx, row in best_value.iterrows():
    print(f"  • {row['name'][:40]}... £{row['price']:.2f} ({row['rating']}⭐)")

# Price outliers
print("\n📈 Price Outliers:")
q1 = df['price'].quantile(0.25)
q3 = df['price'].quantile(0.75)
iqr = q3 - q1
lower_bound = q1 - 1.5 * iqr
upper_bound = q3 + 1.5 * iqr

outliers = df[(df['price'] < lower_bound) | (df['price'] > upper_bound)]
if not outliers.empty:
    print("  Books with unusual prices:")
    for idx, row in outliers.iterrows():
        print(f"  • {row['name'][:40]}... £{row['price']:.2f} ({row['rating']}⭐)")
else:
    print("  No significant price outliers found.")

print("\n" + "="*60)