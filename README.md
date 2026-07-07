# Retail KPI Dashboard with a Single Source of Truth

A data-analytics / data-engineering project that turns a messy raw retail sales
file into a clean **star-schema data model** (the "single source of truth") and
presents the key business metrics in a **Power BI** dashboard.

## The problem this solves
Companies often have sales data spread across messy spreadsheets, where the same
numbers get calculated differently by different people. This project builds ONE
trustworthy, well-structured data model so every KPI comes from the same place.

## Architecture
```
data/raw/raw_sales.csv          <- messy raw data (missing values, dupes, typos)
        |
        |  src/build_star_schema.py  (Python + pandas: clean + model)
        v
data/warehouse/                 <- the SINGLE SOURCE OF TRUTH
   retail.db                       (SQLite database with the star schema)
   dim_product.csv                 (also exported as CSV for Power BI)
   dim_customer.csv
   dim_date.csv
   fact_sales.csv
        |
        |  Power BI (relationships + DAX measures + visuals)
        v
   KPI dashboard
```

## The star schema
```
        dim_date            dim_customer
             \                   /
              \                 /
               \               /
                +--fact_sales--+
               /
              /
       dim_product
```
- **fact_sales** — one row per sale line (quantity, unit_price, revenue) plus keys.
- **dim_product** — product name, category, price.
- **dim_customer** — customer id, country, value segment.
- **dim_date** — day, month, quarter, year, weekday.

## How to run the data pipeline
```bash
python src/generate_raw_data.py    # Step 1: create the messy raw file
python src/build_star_schema.py    # Step 2: clean it + build the star schema
```

## KPIs in the dashboard
- Total Revenue (+ month-over-month growth)
- Revenue by Product Category
- Top 10 Products / Top Customers
- Revenue by Country
- Average Order Value
- Monthly revenue trend

## Tech stack
Python (pandas) · SQLite · SQL · Power BI · Star-schema dimensional modeling

## Project structure
```
retail-kpi-dashboard/
  data/
    raw/          raw messy input
    warehouse/    cleaned star-schema tables (CSV + SQLite)
  src/
    generate_raw_data.py    creates the messy raw data
    build_star_schema.py    the ETL: clean + model
  docs/           schema diagram, screenshots
  README.md
```
