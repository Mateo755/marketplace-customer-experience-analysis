USE olist_analytics;

-- Baseline descriptive analyses (H1–H4).
-- Extended robustness descriptors: see 06_extended_analysis.sql.
-- Formal significance tests: notebooks/02_hypothesis_tests.ipynb.

-- =========================================================
-- Analysis 1: Overall scale of customer dissatisfaction
-- Purpose:
-- Measure the size of the reviewed delivered-order population
-- and summarize the overall level of low customer satisfaction.
-- =========================================================
SELECT
    COUNT(*) AS reviewed_delivered_orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM mart_order_fact
WHERE order_status = 'delivered'
  AND review_score IS NOT NULL;


-- =========================================================
-- Analysis 2: Delivery delay vs. review score
-- Purpose:
-- Evaluate whether worsening delivery performance is associated
-- with lower average reviews and a higher low-review rate.
-- =========================================================
WITH delivery_buckets AS (
    SELECT
        CASE
            WHEN delivery_delay_days <= 0 THEN 'On time or early'
            WHEN delivery_delay_days BETWEEN 1 AND 3 THEN '1-3 days late'
            WHEN delivery_delay_days BETWEEN 4 AND 7 THEN '4-7 days late'
            WHEN delivery_delay_days > 7 THEN '8+ days late'
        END AS delivery_bucket,
        review_score,
        is_low_review
    FROM mart_order_fact
    WHERE order_status = 'delivered'
      AND review_score IS NOT NULL
      AND delivery_delay_days IS NOT NULL
)
SELECT
    delivery_bucket,
    COUNT(*) AS orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM delivery_buckets
GROUP BY delivery_bucket
ORDER BY CASE delivery_bucket
    WHEN 'On time or early' THEN 1
    WHEN '1-3 days late' THEN 2
    WHEN '4-7 days late' THEN 3
    WHEN '8+ days late' THEN 4
END;


-- =========================================================
-- Analysis 3: Product categories with the highest low-review risk
-- Purpose:
-- Identify product categories with elevated dissatisfaction
-- among delivered orders with available reviews.
-- Note:
-- Review score is assigned at the order level, so category-level
-- interpretation should remain directionally useful, not causal.
-- =========================================================
WITH item_reviews AS (
    SELECT
        COALESCE(
            ct.product_category_name_english,
            p.product_category_name,
            'unknown'
        ) AS category,
        r.review_score,
        CASE
            WHEN r.review_score <= 2 THEN 1
            ELSE 0
        END AS is_low_review
    FROM raw_order_items oi
    INNER JOIN raw_orders o
        ON oi.order_id = o.order_id
    INNER JOIN raw_order_reviews r
        ON oi.order_id = r.order_id
    LEFT JOIN raw_products p
        ON oi.product_id = p.product_id
    LEFT JOIN raw_category_translation ct
        ON p.product_category_name = ct.product_category_name
    WHERE o.order_status = 'delivered'
      AND r.review_score IS NOT NULL
)
SELECT
    category,
    COUNT(*) AS items_in_reviewed_orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM item_reviews
GROUP BY category
HAVING COUNT(*) >= 100
ORDER BY low_review_rate_pct DESC, items_in_reviewed_orders DESC
LIMIT 15;


-- =========================================================
-- Analysis 4: Repeat purchase after the first customer experience
-- Purpose:
-- Estimate whether the quality of the first reviewed delivered
-- order is associated with a lower probability of a subsequent order.
-- Note:
-- The date restriction leaves enough time for a potential next order.
-- =========================================================
WITH ranked_orders AS (
    SELECT
        customer_unique_id,
        order_id,
        order_purchase_timestamp,
        review_score,
        ROW_NUMBER() OVER (
            PARTITION BY customer_unique_id
            ORDER BY order_purchase_timestamp
        ) AS order_number,
        LEAD(order_id) OVER (
            PARTITION BY customer_unique_id
            ORDER BY order_purchase_timestamp
        ) AS next_order_id
    FROM mart_order_fact
    WHERE order_status = 'delivered'
),
first_reviewed_orders AS (
    SELECT
        customer_unique_id,
        order_purchase_timestamp,
        review_score,
        next_order_id
    FROM ranked_orders
    WHERE order_number = 1
      AND review_score IS NOT NULL
      AND order_purchase_timestamp < '2018-07-01'
)
SELECT
    CASE
        WHEN review_score <= 2 THEN 'Low review (1-2)'
        WHEN review_score = 3 THEN 'Neutral review (3)'
        WHEN review_score >= 4 THEN 'High review (4-5)'
    END AS first_order_review_group,
    COUNT(*) AS customers,
    SUM(CASE WHEN next_order_id IS NOT NULL THEN 1 ELSE 0 END) AS customers_with_next_order,
    ROUND(
        100.0 * SUM(CASE WHEN next_order_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS repeat_purchase_rate_pct
FROM first_reviewed_orders
GROUP BY first_order_review_group
ORDER BY CASE first_order_review_group
    WHEN 'Low review (1-2)' THEN 1
    WHEN 'Neutral review (3)' THEN 2
    WHEN 'High review (4-5)' THEN 3
END;


-- =========================================================
-- Analysis 5: Seller-level risk diagnostic
-- Purpose:
-- Identify sellers with persistently elevated low-review rates
-- among sellers with a meaningful order volume.
-- Note:
-- This is a diagnostic view only. Review scores are recorded at
-- the order level, so seller-level attribution is imperfect.
-- =========================================================
WITH seller_metrics AS (
    SELECT
        oi.seller_id,
        COUNT(DISTINCT oi.order_id) AS delivered_orders,
        AVG(r.review_score) AS avg_review_score,
        AVG(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) AS low_review_rate,
        AVG(
            CASE
                WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1
                ELSE 0
            END
        ) AS late_delivery_rate
    FROM raw_order_items oi
    INNER JOIN raw_orders o
        ON oi.order_id = o.order_id
    INNER JOIN raw_order_reviews r
        ON oi.order_id = r.order_id
    WHERE o.order_status = 'delivered'
      AND r.review_score IS NOT NULL
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
    GROUP BY oi.seller_id
)
SELECT
    seller_id,
    delivered_orders,
    ROUND(avg_review_score, 2) AS avg_review_score,
    ROUND(100.0 * low_review_rate, 2) AS low_review_rate_pct,
    ROUND(100.0 * late_delivery_rate, 2) AS late_delivery_rate_pct
FROM seller_metrics
WHERE delivered_orders >= 50
ORDER BY low_review_rate DESC, late_delivery_rate DESC
LIMIT 20;