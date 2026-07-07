"""
build_star_schema.py
--------------------------------------------------------------
STEP 2 of the pipeline -- the CORE of the whole project.

It takes the messy raw file and turns it into a clean STAR SCHEMA:

        dim_date          dim_customer
             \\               /
              \\             /
               fact_sales
              /             \\
             /               \\
      dim_product      (numbers: quantity, revenue)

WHAT IS A STAR SCHEMA?
  - ONE "fact" table  = the events we measure (each sale line: quantity, revenue).
  - SEVERAL "dimension" tables = the context (who / what / when).
  Each dimension value is stored ONCE and linked by an ID (a "key").
  This is the industry-standard way to model data for dashboards, and it is
  what makes our numbers a single, trustworthy "source of truth".

We save the result in TWO forms:
  1. A SQLite database  (data/warehouse/retail.db)  -> the "single source of truth".
  2. One CSV per table   (data/warehouse/*.csv)      -> easy to load into Power BI.

Run it with:   python src/build_star_schema.py
--------------------------------------------------------------
"""

import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "raw_sales.csv"
WAREHOUSE = ROOT / "data" / "warehouse"

# ===============================================================
# 1. EXTRACT -- read the raw file
# ===============================================================
df = pd.read_csv(RAW)
print(f"Loaded raw rows: {len(df)}")

# ===============================================================
# 2. TRANSFORM / CLEAN -- fix every problem we planted
# ===============================================================

# 2a. Remove exact duplicate rows
before = len(df)
df = df.drop_duplicates()
print(f"Removed {before - len(df)} duplicate rows")

# 2b. Fix "N/A" text in UnitPrice, then make it a real number.
#     Rows where the price can't be parsed are dropped (can't value a sale
#     with no price).
df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
df = df.dropna(subset=["UnitPrice"])

# 2c. Standardise Country spelling/casing to one clean value each.
country_fix = {
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "usa": "United States",
    "us": "United States",
}
df["Country"] = df["Country"].str.strip()
df["Country"] = df["Country"].replace(
    {k.title(): v for k, v in country_fix.items()}   # handle title-cased typos too
)
df["Country"] = df["Country"].str.lower().map(country_fix).fillna(df["Country"])
df["Country"] = df["Country"].str.title()

# 2d. Fix Description: standardise casing; fill missing ones using the
#     product's known name (looked up from StockCode).
df["Description"] = df["Description"].str.title()
name_by_code = (
    df.dropna(subset=["Description"])
      .groupby("StockCode")["Description"].agg(lambda s: s.mode().iloc[0])
)
df["Description"] = df["Description"].fillna(df["StockCode"].map(name_by_code))

# 2e. Missing CustomerID -> label as "GUEST" (a common real-world choice:
#     keep the sale, mark the customer as unknown, don't throw money away).
df["CustomerID"] = df["CustomerID"].fillna("GUEST")

# 2f. Parse the date properly so we can build a date dimension.
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
df = df.dropna(subset=["InvoiceDate"])

# 2g. Separate RETURNS (negative quantity) from SALES. For this KPI project
#     we keep only actual sales so revenue is clean. (You could later add a
#     "returns" analysis -- a nice extension.)
df = df[df["Quantity"] > 0]

print(f"Clean rows remaining: {len(df)}")

# ===============================================================
# 3. BUILD THE DIMENSION TABLES
#    Each gets a SURROGATE KEY: a simple integer id we create ourselves.
# ===============================================================

# ---- dim_product ----
# One row per product: its name, category and typical price.
dim_product = (
    df.groupby("StockCode")
      .agg(Description=("Description", "first"),
           Category=("Category", "first"),
           UnitPrice=("UnitPrice", "median"))
      .reset_index()
)
dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))

# ---- dim_customer ----
dim_customer = (
    df.groupby("CustomerID")
      .agg(Country=("Country", lambda s: s.mode().iloc[0]))
      .reset_index()
      .rename(columns={"CustomerID": "customer_id"})
)
# A simple business segment based on how much each customer spent.
spend = (df.assign(rev=df["Quantity"] * df["UnitPrice"])
           .groupby("CustomerID")["rev"].sum())
def segment(cid):
    if cid == "GUEST":
        return "Guest"
    total = spend.get(cid, 0)
    if total >= spend.quantile(0.75):
        return "High Value"
    if total >= spend.quantile(0.40):
        return "Regular"
    return "Occasional"
dim_customer["Segment"] = dim_customer["customer_id"].map(segment)
dim_customer.insert(0, "customer_key", range(1, len(dim_customer) + 1))

# ---- dim_date ----
dates = pd.DataFrame({"full_date": pd.to_datetime(sorted(df["InvoiceDate"].dt.normalize().unique()))})
dates["date_key"]   = dates["full_date"].dt.strftime("%Y%m%d").astype(int)  # e.g. 20240115
dates["day"]        = dates["full_date"].dt.day
dates["month"]      = dates["full_date"].dt.month
dates["month_name"] = dates["full_date"].dt.strftime("%b")
dates["quarter"]    = "Q" + dates["full_date"].dt.quarter.astype(str)
dates["year"]       = dates["full_date"].dt.year
dates["weekday"]    = dates["full_date"].dt.strftime("%A")
dim_date = dates[["date_key", "full_date", "day", "month", "month_name",
                  "quarter", "year", "weekday"]]

# ===============================================================
# 4. BUILD THE FACT TABLE
#    Replace the real-world values with the surrogate keys, and compute revenue.
# ===============================================================
fact = df.copy()
fact["date_key"] = fact["InvoiceDate"].dt.strftime("%Y%m%d").astype(int)
fact = fact.merge(dim_product[["StockCode", "product_key"]], on="StockCode", how="left")
fact = fact.merge(
    dim_customer[["customer_id", "customer_key"]],
    left_on="CustomerID", right_on="customer_id", how="left"
)
fact["revenue"] = fact["Quantity"] * fact["UnitPrice"]

fact_sales = fact[["InvoiceNo", "product_key", "customer_key", "date_key",
                   "Quantity", "UnitPrice", "revenue"]].copy()
fact_sales = fact_sales.rename(columns={
    "InvoiceNo": "invoice_no", "Quantity": "quantity", "UnitPrice": "unit_price"
})
fact_sales.insert(0, "sale_id", range(1, len(fact_sales) + 1))

# ===============================================================
# 5. LOAD -- save to SQLite (source of truth) AND to CSV (for Power BI)
# ===============================================================
WAREHOUSE.mkdir(parents=True, exist_ok=True)

db_path = WAREHOUSE / "retail.db"
conn = sqlite3.connect(db_path)
tables = {
    "dim_product": dim_product,
    "dim_customer": dim_customer,
    "dim_date": dim_date,
    "fact_sales": fact_sales,
}
for name, table in tables.items():
    table.to_sql(name, conn, if_exists="replace", index=False)
    table.to_csv(WAREHOUSE / f"{name}.csv", index=False)
conn.close()

# ===============================================================
# 6. Report what we built
# ===============================================================
print("\n=== STAR SCHEMA BUILT ===")
for name, table in tables.items():
    print(f"  {name:13s}: {len(table):5d} rows, {table.shape[1]} columns")
print(f"\nSQLite database : {db_path}")
print(f"CSV files       : {WAREHOUSE}")

total_rev = fact_sales["revenue"].sum()
print(f"\nSanity check -> Total revenue across all sales: Rs {total_rev:,.0f}")
