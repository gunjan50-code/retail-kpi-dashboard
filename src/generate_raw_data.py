"""
generate_raw_data.py
--------------------------------------------------------------
STEP 1 of the pipeline.

This script creates a REALISTIC, MESSY retail sales file, just like the
raw data a company would dump on your desk. We deliberately add problems
(missing values, inconsistent spelling, duplicates, returns) so that our
cleaning step in the next script has something real to fix.

The output columns mimic the famous "Online Retail" dataset used in industry:
    InvoiceNo, StockCode, Description, Quantity, InvoiceDate,
    UnitPrice, CustomerID, Country

Run it with:   python src/generate_raw_data.py
Output:        data/raw/raw_sales.csv
--------------------------------------------------------------
"""

import numpy as np
import pandas as pd
from pathlib import Path

# A fixed random seed means you get the SAME data every time you run it.
# That's good for a project you want to be reproducible.
rng = np.random.default_rng(42)

# ---------------------------------------------------------------
# 1. A small, clean PRODUCT CATALOG.
#    Each product has a code, a name, a category, and a base price.
# ---------------------------------------------------------------
catalog = [
    ("SKU-1001", "Wireless Mouse",        "Electronics", 799),
    ("SKU-1002", "Mechanical Keyboard",   "Electronics", 2499),
    ("SKU-1003", "USB-C Cable",           "Electronics", 299),
    ("SKU-1004", "Laptop Stand",          "Accessories", 1299),
    ("SKU-1005", "Notebook A5",           "Stationery",  149),
    ("SKU-1006", "Gel Pen Pack",          "Stationery",  99),
    ("SKU-1007", "Water Bottle 1L",       "Home",        399),
    ("SKU-1008", "Coffee Mug",            "Home",        249),
    ("SKU-1009", "Desk Lamp",             "Home",        1499),
    ("SKU-1010", "Backpack",              "Accessories", 1999),
    ("SKU-1011", "Wireless Earbuds",      "Electronics", 3499),
    ("SKU-1012", "Phone Case",            "Accessories", 499),
    ("SKU-1013", "Sticky Notes",          "Stationery",  79),
    ("SKU-1014", "Power Bank 10000mAh",   "Electronics", 1799),
    ("SKU-1015", "Yoga Mat",              "Home",        899),
]
catalog_df = pd.DataFrame(catalog, columns=["StockCode", "Description", "Category", "UnitPrice"])

# ---------------------------------------------------------------
# 2. A small set of CUSTOMERS, each based in a country.
# ---------------------------------------------------------------
countries = ["India", "United Kingdom", "Germany", "France", "United States"]
customer_ids = [f"C{n:04d}" for n in range(1, 121)]   # 120 customers: C0001..C0120
customer_country = {cid: rng.choice(countries) for cid in customer_ids}

# ---------------------------------------------------------------
# 3. Generate TRANSACTIONS (one row = one product on one invoice).
# ---------------------------------------------------------------
N = 6000
rows = []
date_range = pd.date_range("2024-01-01", "2024-12-31", freq="D")

for i in range(N):
    prod = catalog_df.iloc[rng.integers(0, len(catalog_df))]
    cust = rng.choice(customer_ids)
    invoice_no = f"INV{100000 + rng.integers(0, 4000)}"   # some invoices repeat -> multi-item baskets
    qty = int(rng.integers(1, 12))
    date = rng.choice(date_range)
    rows.append({
        "InvoiceNo":   invoice_no,
        "StockCode":   prod["StockCode"],
        "Description": prod["Description"],
        "Category":    prod["Category"],
        "Quantity":    qty,
        "InvoiceDate": pd.Timestamp(date).strftime("%Y-%m-%d %H:%M"),
        "UnitPrice":   prod["UnitPrice"],
        "CustomerID":  cust,
        "Country":     customer_country[cust],
    })

df = pd.DataFrame(rows)

# ---------------------------------------------------------------
# 4. NOW WE MAKE IT MESSY (this is what makes the project realistic).
# ---------------------------------------------------------------

# 4a. Inconsistent country spelling / casing
df.loc[df.sample(frac=0.05, random_state=1).index, "Country"] = "united kingdom"
df.loc[df.sample(frac=0.03, random_state=2).index, "Country"] = "USA"   # should be "United States"

# 4b. Missing CustomerID on some rows (very common in real data)
df.loc[df.sample(frac=0.06, random_state=3).index, "CustomerID"] = np.nan

# 4c. Missing / inconsistent Description
df.loc[df.sample(frac=0.02, random_state=4).index, "Description"] = np.nan
df.loc[df.sample(frac=0.03, random_state=5).index, "Description"] = df["Description"].str.upper()

# 4d. Some RETURNS: negative quantity (real retail data has these)
ret_idx = df.sample(frac=0.03, random_state=6).index
df.loc[ret_idx, "Quantity"] = -df.loc[ret_idx, "Quantity"].abs()

# 4e. A few "N/A" strings instead of proper nulls in UnitPrice.
#     (We cast the column to 'object' first so mixing text with numbers is allowed.)
df["UnitPrice"] = df["UnitPrice"].astype(object)
na_idx = df.sample(frac=0.01, random_state=7).index
df.loc[na_idx, "UnitPrice"] = "N/A"

# 4f. Duplicate rows (accidental double-entry)
dupes = df.sample(frac=0.02, random_state=8)
df = pd.concat([df, dupes], ignore_index=True)

# Shuffle so the messiness isn't all at the bottom
df = df.sample(frac=1, random_state=9).reset_index(drop=True)

# ---------------------------------------------------------------
# 5. Save the raw file.
# ---------------------------------------------------------------
out = Path(__file__).resolve().parents[1] / "data" / "raw" / "raw_sales.csv"
df.to_csv(out, index=False)

print(f"Created messy raw data: {out}")
print(f"Rows: {len(df)}")
print("\nA peek at the raw data:")
print(df.head(8).to_string(index=False))
