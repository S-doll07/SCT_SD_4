"""
Category Analysis - Find patterns in book categories
"""

import pandas as pd
import glob
import matplotlib.pyplot as plt

# Find latest CSV
csv_files = glob.glob('products_*.csv')
if not csv_files:
    print("No CSV files found!")
    exit()

latest_csv = sorted(csv_files)[-1]
df = pd.read_csv(latest_csv)

print("="*60)
print("📊 CATEGORY ANALYSIS")
print("="*60)

# Clean up "Default" category - try to map from description
def get_real_category(row):
    if row['category'] == 'Default':
        # Try to infer from description
        desc = str(row['description']).lower()
        if 'fiction' in desc:
            return 'Fiction'
        elif 'history' in desc or 'historical' in desc:
            return 'History'
        elif 'poetry' in desc:
            return 'Poetry'
        elif 'mystery' in desc or 'thriller' in desc:
            return 'Mystery'
        elif 'business' in desc or 'career' in desc:
            return 'Business'
        elif 'young' in desc or 'teen' in desc:
            return 'Young Adult'
        else:
            return 'Uncategorized'
    return row['category']

df['real_category'] = df.apply(get_real_category, axis=1)

# Category counts
print("\n📂 Books by Category:")
category_counts = df['real_category'].value_counts()
for cat, count in category_counts.items():
    print(f"  • {cat}: {count} books ({count/len(df)*100:.1f}%)")

# Average price by category
print("\n💰 Average Price by Category:")
avg_price_by_cat = df.groupby('real_category')['price'].mean().sort_values(ascending=False)
for cat, price in avg_price_by_cat.items():
    print(f"  • {cat}: £{price:.2f}")

# Average rating by category
print("\n⭐ Average Rating by Category:")
avg_rating_by_cat = df.groupby('real_category')['rating'].mean().sort_values(ascending=False)
for cat, rating in avg_rating_by_cat.items():
    print(f"  • {cat}: {rating:.1f} stars")

# Create charts
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Category counts
category_counts.plot(kind='bar', ax=axes[0], color='skyblue')
axes[0].set_title('Books by Category')
axes[0].set_xlabel('Category')
axes[0].set_ylabel('Number of Books')
axes[0].tick_params(axis='x', rotation=45)

# Average price by category
avg_price_by_cat.plot(kind='bar', ax=axes[1], color='lightgreen')
axes[1].set_title('Average Price by Category')
axes[1].set_xlabel('Category')
axes[1].set_ylabel('Average Price (£)')
axes[1].tick_params(axis='x', rotation=45)

# Price vs Rating scatter
df.plot(kind='scatter', x='price', y='rating', ax=axes[2], alpha=0.7)
axes[2].set_title('Price vs Rating')
axes[2].set_xlabel('Price (£)')
axes[2].set_ylabel('Rating (Stars)')

plt.tight_layout()
plt.savefig('category_analysis.png', dpi=150, bbox_inches='tight')
print("\n📊 Chart saved: category_analysis.png")
print("="*60)