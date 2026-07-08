"""Generate a messy synthetic retail sales file for the cleaning pipeline.

Output columns follow the "Online Retail" dataset layout:
InvoiceNo, StockCode, Description, Category, Quantity, InvoiceDate,
UnitPrice, CustomerID, Country.
"""

import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)

catalog = pd.DataFrame(
    [
        ("SKU-1001", "Wireless Mouse",      "Electronics", 799),
        ("SKU-1002", "Mechanical Keyboard", "Electronics", 2499),
        ("SKU-1003", "USB-C Cable",         "Electronics", 299),
        ("SKU-1004", "Laptop Stand",        "Accessories", 1299),
        ("SKU-1005", "Notebook A5",         "Stationery",  149),
        ("SKU-1006", "Gel Pen Pack",        "Stationery",  99),
        ("SKU-1007", "Water Bottle 1L",     "Home",        399),
        ("SKU-1008", "Coffee Mug",          "Home",        249),
        ("SKU-1009", "Desk Lamp",           "Home",        1499),
        ("SKU-1010", "Backpack",            "Accessories", 1999),
        ("SKU-1011", "Wireless Earbuds",    "Electronics", 3499),
        ("SKU-1012", "Phone Case",          "Accessories", 499),
        ("SKU-1013", "Sticky Notes",        "Stationery",  79),
        ("SKU-1014", "Power Bank 10000mAh", "Electronics", 1799),
        ("SKU-1015", "Yoga Mat",            "Home",        899),
    ],
    columns=["StockCode", "Description", "Category", "UnitPrice"],
)

countries = ["India", "United Kingdom", "Germany", "France", "United States"]
customer_ids = [f"C{n:04d}" for n in range(1, 121)]
customer_country = {cid: rng.choice(countries) for cid in customer_ids}

dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")

rows = []
for _ in range(6000):
    prod = catalog.iloc[rng.integers(0, len(catalog))]
    cust = rng.choice(customer_ids)
    rows.append({
        "InvoiceNo": f"INV{100000 + rng.integers(0, 4000)}",
        "StockCode": prod["StockCode"],
        "Description": prod["Description"],
        "Category": prod["Category"],
        "Quantity": int(rng.integers(1, 12)),
        "InvoiceDate": pd.Timestamp(rng.choice(dates)).strftime("%Y-%m-%d %H:%M"),
        "UnitPrice": prod["UnitPrice"],
        "CustomerID": cust,
        "Country": customer_country[cust],
    })

df = pd.DataFrame(rows)

# Introduce realistic data-quality problems.
df.loc[df.sample(frac=0.05, random_state=1).index, "Country"] = "united kingdom"
df.loc[df.sample(frac=0.03, random_state=2).index, "Country"] = "USA"
df.loc[df.sample(frac=0.06, random_state=3).index, "CustomerID"] = np.nan
df.loc[df.sample(frac=0.02, random_state=4).index, "Description"] = np.nan
df.loc[df.sample(frac=0.03, random_state=5).index, "Description"] = df["Description"].str.upper()

returns = df.sample(frac=0.03, random_state=6).index
df.loc[returns, "Quantity"] = -df.loc[returns, "Quantity"].abs()

df["UnitPrice"] = df["UnitPrice"].astype(object)
df.loc[df.sample(frac=0.01, random_state=7).index, "UnitPrice"] = "N/A"

df = pd.concat([df, df.sample(frac=0.02, random_state=8)], ignore_index=True)
df = df.sample(frac=1, random_state=9).reset_index(drop=True)

out = Path(__file__).resolve().parents[1] / "data" / "raw" / "raw_sales.csv"
df.to_csv(out, index=False)
print(f"Wrote {len(df)} rows to {out}")
