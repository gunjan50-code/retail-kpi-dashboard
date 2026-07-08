"""Clean the raw sales file and build a star schema.

Produces fact_sales plus dim_product, dim_customer and dim_date, saved to a
SQLite database and to one CSV per table (for Power BI).
"""

import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "raw_sales.csv"
WAREHOUSE = ROOT / "data" / "warehouse"

df = pd.read_csv(RAW)
df = df.drop_duplicates()

# UnitPrice has some "N/A" text; keep only rows with a real price.
df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
df = df.dropna(subset=["UnitPrice"])

# Standardise country names.
country_fix = {
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "usa": "United States",
    "us": "United States",
}
country = df["Country"].str.strip()
df["Country"] = country.str.lower().map(country_fix).fillna(country.str.title())

# Fix casing on Description and fill blanks from the product's known name.
df["Description"] = df["Description"].str.title()
name_by_code = (
    df.dropna(subset=["Description"])
      .groupby("StockCode")["Description"].agg(lambda s: s.mode().iloc[0])
)
df["Description"] = df["Description"].fillna(df["StockCode"].map(name_by_code))

df["CustomerID"] = df["CustomerID"].fillna("GUEST")
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
df = df.dropna(subset=["InvoiceDate"])

# Drop returns (negative quantity) so revenue stays clean.
df = df[df["Quantity"] > 0]

dim_product = (
    df.groupby("StockCode")
      .agg(Description=("Description", "first"),
           Category=("Category", "first"),
           UnitPrice=("UnitPrice", "median"))
      .reset_index()
)
dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))

spend = (df.assign(rev=df["Quantity"] * df["UnitPrice"])
           .groupby("CustomerID")["rev"].sum())
high, mid = spend.quantile(0.75), spend.quantile(0.40)

def segment(cid):
    if cid == "GUEST":
        return "Guest"
    total = spend.get(cid, 0)
    if total >= high:
        return "High Value"
    if total >= mid:
        return "Regular"
    return "Occasional"

dim_customer = (
    df.groupby("CustomerID")
      .agg(Country=("Country", lambda s: s.mode().iloc[0]))
      .reset_index()
      .rename(columns={"CustomerID": "customer_id"})
)
dim_customer["Segment"] = dim_customer["customer_id"].map(segment)
dim_customer.insert(0, "customer_key", range(1, len(dim_customer) + 1))

dim_date = pd.DataFrame(
    {"full_date": pd.to_datetime(sorted(df["InvoiceDate"].dt.normalize().unique()))}
)
dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
dim_date["day"] = dim_date["full_date"].dt.day
dim_date["month"] = dim_date["full_date"].dt.month
dim_date["month_name"] = dim_date["full_date"].dt.strftime("%b")
dim_date["quarter"] = "Q" + dim_date["full_date"].dt.quarter.astype(str)
dim_date["year"] = dim_date["full_date"].dt.year
dim_date["weekday"] = dim_date["full_date"].dt.strftime("%A")
dim_date = dim_date[["date_key", "full_date", "day", "month", "month_name",
                     "quarter", "year", "weekday"]]

fact = df.merge(dim_product[["StockCode", "product_key"]], on="StockCode")
fact = fact.merge(dim_customer[["customer_id", "customer_key"]],
                  left_on="CustomerID", right_on="customer_id")
fact["date_key"] = fact["InvoiceDate"].dt.strftime("%Y%m%d").astype(int)
fact["revenue"] = fact["Quantity"] * fact["UnitPrice"]

fact_sales = fact[["InvoiceNo", "product_key", "customer_key", "date_key",
                   "Quantity", "UnitPrice", "revenue"]].rename(columns={
    "InvoiceNo": "invoice_no", "Quantity": "quantity", "UnitPrice": "unit_price",
})
fact_sales.insert(0, "sale_id", range(1, len(fact_sales) + 1))

WAREHOUSE.mkdir(parents=True, exist_ok=True)
tables = {
    "dim_product": dim_product,
    "dim_customer": dim_customer,
    "dim_date": dim_date,
    "fact_sales": fact_sales,
}
conn = sqlite3.connect(WAREHOUSE / "retail.db")
for name, table in tables.items():
    table.to_sql(name, conn, if_exists="replace", index=False)
    table.to_csv(WAREHOUSE / f"{name}.csv", index=False)
conn.close()

for name, table in tables.items():
    print(f"{name}: {len(table)} rows")
print(f"Total revenue: {fact_sales['revenue'].sum():,.0f}")
