# Marketplace Customer Experience Analysis

## Business question

Which operational factors are associated with poor customer reviews, and how could a marketplace prioritize initiatives to improve customer experience and repeat purchasing?

## Executive summary

This project analyzes marketplace customer experience using the Olist dataset. The strongest risk factor associated with poor reviews is delivery delay. Late deliveries are linked to a sharp increase in low-review rates, while some product categories and sellers show elevated risk as secondary signals.

The analysis suggests that logistics reliability should be the first operational priority. Category- and seller-level differences are useful diagnostic signals, while first-order experience quality may also be linked to future purchasing behavior.

## Project overview

This project analyzes a public marketplace dataset to investigate how delivery performance, product category, and seller-level variation are associated with customer satisfaction. The analytical focus is on four business questions:

1. Does delivery delay correlate with a higher share of low review scores?
2. Which product categories are associated with elevated customer dissatisfaction?
3. Are customers less likely to place another order after a poor first experience?
4. Which sellers show persistently elevated risk of poor customer outcomes?

The project was built in MySQL 8 and Python, with a dedicated order-level analytical view used as the basis for downstream analysis. MySQL 8 supports window functions, which makes it suitable for customer-level sequence analysis such as first-order and repeat-purchase logic.

## Dataset

This project uses the **Brazilian E-Commerce Public Dataset by Olist**, a public marketplace dataset available on Kaggle. The dataset contains approximately 100,000 orders with information on customers, products, order items, delivery timestamps, and review scores.

Required source files:

- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_products_dataset.csv`
- `product_category_name_translation.csv`

## Tech stack

- **Database:** MySQL 8
- **SQL:** CTEs, multi-table joins, aggregations, window functions
- **Python:** pandas, matplotlib, seaborn
- **Environment:** Jupyter Notebook
- **Version control:** Git, GitHub

## Repository structure

```text
marketplace-customer-experience-analysis/
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── raw/
│   ├── processed/
│   └── README.md
├── docs/
│   └── methodology.md
├── notebooks/
│   └── 01_visualizations.ipynb
├── outputs/
│   ├── delivery_delay_vs_reviews.jpg
│   ├── category_low_review_risk.jpg
│   ├── repeat_purchase_by_review.jpg
│   └── seller_low_review_risk.jpg
└── sql/
    ├── 00_create_database.sql
    ├── 01_create_tables.sql
    ├── 02_load_data.sql
    ├── 03_create_mart.sql
    ├── 04_quality_checks.sql
    └── 05_analysis.sql
```

## Analytical approach

The analysis was performed in the following order:

1. Imported raw CSV files into MySQL 8 tables.
2. Created an order-level analytical view called `mart_order_fact`.
3. Validated granularity, missing values, and delivery-time ranges.
4. Analyzed the relationship between delivery delay and review score.
5. Identified product categories with elevated low-review rates.
6. Estimated repeat-purchase rate based on the review score of the customer’s first order.
7. Added an optional seller-level diagnostic analysis for sellers with at least 50 delivered reviewed orders.
8. Exported query outputs and built final visualizations in Python.

The core analytical unit is a single order (`order_id`). This prevents row multiplication caused by joining order-level and item-level tables directly in downstream analysis.

## Data quality checks

Before running the business analysis, the analytical view `mart_order_fact` was validated to confirm correct granularity and data coverage.

- Verified that `mart_order_fact` contains exactly one row per order: **99,441 rows** and **99,441 unique `order_id` values**, with **0 duplicate rows**.
- Checked order-status distribution and confirmed that the dataset is dominated by **delivered orders (96,478)**, with smaller volumes of shipped, canceled, unavailable, invoiced, processing, created, and approved orders.
- Assessed missing values relevant to customer-experience analysis: **769 orders without review score**, **2,965 without delivery date**, and **775 without item-level data**.
- Inspected delivery-time ranges and delivery-delay ranges before building delivery buckets.
- Reviewed the distribution of review scores and confirmed that the dataset is strongly skewed toward high ratings, especially score 5.

For customer-experience analyses, the final population was restricted to **delivered orders with an available review score**.

## Key findings

- Across **95,831 delivered orders with a review score**, the average review score was **4.16**, while the low-review rate (defined as score <= 2) was **12.77%**.
- Delivery performance showed the strongest relationship with customer dissatisfaction. Orders delivered **on time or early** had an average review score of **4.29** and a low-review rate of **9.23%**, while orders delivered **8+ days late** had an average review score of **1.70** and a low-review rate of **79.18%**.
- Intermediate delay buckets also showed a clear monotonic deterioration: **1-3 days late** orders had a low-review rate of **32.18%**, and **4-7 days late** orders reached **67.56%**.
- The highest-risk product categories among categories with at least 100 reviewed delivered items were **office_furniture** (**25.42%** low-review rate), **fashion_male_clothing** (**25.00%**), **fixed_telephony** (**22.92%**), **audio** (**21.73%**), and **home_confort** (**19.77%**).
- Customers whose first delivered reviewed order received a **low review (1-2)** had a repeat-purchase rate of **2.96%**, compared with **3.00%** for **neutral reviews (3)** and **3.36%** for **high reviews (4-5)**.
- An additional seller-level analysis identified substantial variation in low-review rates among sellers with at least 50 delivered reviewed orders, ranging from **28.74%** to **63.49%**. This suggests that some seller-level operational or quality issues may contribute disproportionately to poor customer outcomes.
- The repeat-purchase gap is smaller than the delivery-delay effect on reviews, but it still suggests that first-order experience quality is associated with future purchasing behavior.

## Business interpretation

The results suggest that **delivery delay is the clearest operational signal linked to customer dissatisfaction** in this dataset. The sharp increase in low-review rate as lateness grows indicates that logistics reliability is likely more important for customer experience than many category-level differences.

Category-level variation still matters, especially in product groups such as office furniture, fixed telephony, and audio, where dissatisfaction rates are elevated even after filtering for minimum transaction volume. These categories may require deeper investigation into product quality, damage risk, packaging, or expectation setting.

The repeat-purchase analysis suggests that a poor first experience is associated with lower follow-up purchasing. Although the absolute differences are modest, this finding supports the idea that customer experience metrics are not only service indicators, but also early signals of retention risk.

The seller-level analysis works best as an operational diagnostic layer rather than a definitive performance ranking. Large variation between sellers may reflect differences in fulfillment quality, packaging, or product expectations, but seller-level interpretation must remain cautious because reviews are attached to orders rather than isolated seller interactions.

## Key analyses

### 1. Delivery delay vs. customer dissatisfaction

Orders were grouped into delivery-delay buckets:

- On time or early
- 1-3 days late
- 4-7 days late
- 8+ days late

For each bucket, the analysis measured:

- number of orders,
- average review score,
- low-review rate, defined as review score <= 2.

This analysis shows whether operational delivery performance is associated with worse customer outcomes.

### 2. Product categories with elevated low-review rates

Item-level data were joined with translated product categories and order-level review scores. Categories with small sample sizes were filtered out using a minimum-volume threshold to reduce unstable ranking effects.

For each category, the analysis measured:

- number of items in reviewed delivered orders,
- average review score,
- low-review rate.

This makes it possible to identify which product areas may require deeper investigation into quality, packaging, expectation setting, or logistics.

### 3. Repeat-purchase rate after the first customer experience

Customer order history was analyzed using window functions in MySQL 8. For each customer, the first delivered reviewed order was identified, and the presence of a subsequent order was used to estimate repeat-purchase behavior.

Customers were grouped by the review score of their first order:

- Low review (1-2)
- Neutral review (3)
- High review (4-5)

This analysis helps connect customer experience with future purchasing behavior.

### 4. Seller-level low-review risk analysis

As an additional diagnostic layer, the project also evaluates seller-level patterns among sellers with at least 50 delivered reviewed orders.

For each seller, the analysis measures:

- number of delivered reviewed orders,
- average review score,
- low-review rate,
- late-delivery rate.

This view helps identify sellers with consistently poor customer outcomes and supports operational prioritization. However, seller-level interpretation should remain cautious because review scores are assigned at the order level and may reflect multiple items or sellers within the same order.

## Recommendations

### Business recommendations by priority

1. **Reduce delivery lateness first.** Delivery delay has the clearest association with poor reviews, especially once lateness exceeds 3 days.
2. **Audit high-risk categories.** Categories such as office furniture, fashion male clothing, fixed telephony, audio, and home confort should be reviewed for product quality, packaging, and expectation-setting issues.
3. **Use seller-level monitoring as a diagnostic layer.** Large differences in low-review rates can help identify seller groups that may require operational review or support.
4. **Monitor first-order experience as a retention signal.** Even small repeat-purchase differences suggest that poor early experiences may weaken customer retention.

## How I would extend this analysis

- Add payment type, price, and freight value to test whether dissatisfaction is driven by value perception as well as delay.
- Segment delivery performance by region to see whether the problem is concentrated geographically.
- Build a simple predictive model for low review risk to quantify feature importance.
- Measure time to repeat purchase instead of only presence of a subsequent order.
- Test whether proactive communication reduces the impact of delay on review scores.

## Data dictionary

- `mart_order_fact`: one row per order, used as the main analytical mart.
- `review_score`: customer review score on a 1-5 scale.
- `is_low_review`: binary flag where 1 means review score <= 2.
- `delivery_days`: delivered date minus purchase date.
- `delivery_delay_days`: delivered date minus estimated delivery date.
- `order_item_count`: number of items in the order.

## Visualizations

The final notebook generates four business-oriented visualizations:

1. **Low-review rate by delivery-delay bucket**
2. **Categories with the highest low-review rate**
3. **Repeat-purchase rate by first-order review group**
4. **Sellers with the highest low-review rate**

These visual outputs are stored in the `outputs/` directory.

### Figures

![Low-review rate by delivery-delay bucket](outputs/delivery_delay_vs_reviews.png)

![Categories with the highest low-review rate](outputs/category_low_review_risk.png)

![Repeat-purchase rate by first-order review group](outputs/repeat_purchase_by_review.png)

![Sellers with the highest low-review rate](outputs/seller_low_review_risk.png)

## Main SQL concepts demonstrated

This project demonstrates practical SQL skills relevant to analytics work:

- multi-table `JOIN`
- Common Table Expressions (CTEs)
- aggregations and grouped metrics
- analytical filtering with `HAVING`
- delivery-time calculations with date functions
- window functions such as `ROW_NUMBER()` and `LEAD()`
- construction of an order-level analytical layer for downstream analysis
- seller-level diagnostic aggregation with operational risk metrics

## Limitations

- The analysis is observational and identifies associations, not causal effects.
- Not every order has a review score, which may introduce selection bias.
- Review score is measured at the order level rather than the individual item level.
- In multi-item or multi-seller contexts, review attribution is imperfect.
- Seller-level results should be interpreted cautiously because a review score may reflect the combined experience of an order rather than the performance of a single seller.
- The repeat-purchase analysis captures whether a later order exists, but not the time to repurchase or the full customer lifetime value.
- The dataset represents a historical Brazilian marketplace and should not be generalized directly to another platform.

## Reproduction steps

1. Download the required Olist dataset files from Kaggle.
2. Place the required CSV files in `data/raw/`.
3. Run SQL scripts in the following order:

```text
00_create_database.sql
01_create_tables.sql
02_load_data.sql
03_create_mart.sql
04_quality_checks.sql
05_analysis.sql
```

4. Export analysis outputs to `data/processed/`.
5. Run `notebooks/01_visualizations.ipynb` to generate final charts.

## Why this project matters

This project was designed as a product/data analytics portfolio piece rather than a generic SQL exercise. It focuses on a realistic business problem, validates data quality before interpretation, and translates relational data into customer-experience insights and actionable marketplace recommendations.
