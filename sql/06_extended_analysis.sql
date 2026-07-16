USE olist_analytics;

-- =========================================================
-- Extended analysis: H5–H12 robustness / diagnostic layers
-- Baseline associations live in 05_analysis.sql (H1–H4).
-- Population default: delivered orders with a review score.
-- =========================================================


-- =========================================================
-- H5: Regional variation in late delivery and low reviews
-- =========================================================
SELECT
    customer_state,
    COUNT(*) AS orders,
    ROUND(100.0 * AVG(is_late_delivery), 2) AS late_delivery_rate_pct,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM mart_order_fact
WHERE order_status = 'delivered'
  AND review_score IS NOT NULL
  AND is_late_delivery IS NOT NULL
GROUP BY customer_state
HAVING COUNT(*) >= 200
ORDER BY low_review_rate_pct DESC, orders DESC;


-- H5 context: late vs on-time low-review rate within each state
SELECT
    customer_state,
    CASE WHEN is_late_delivery = 1 THEN 'Late' ELSE 'On time or early' END AS delivery_status,
    COUNT(*) AS orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM mart_order_fact
WHERE order_status = 'delivered'
  AND review_score IS NOT NULL
  AND is_late_delivery IS NOT NULL
  AND customer_state IN (
      SELECT customer_state
      FROM mart_order_fact
      WHERE order_status = 'delivered'
        AND review_score IS NOT NULL
        AND is_late_delivery IS NOT NULL
      GROUP BY customer_state
      HAVING COUNT(*) >= 200
  )
GROUP BY customer_state, delivery_status
ORDER BY customer_state, delivery_status;


-- =========================================================
-- H6/H7: Freight-ratio terciles vs low-review rate
-- One simple axis only (freight / item revenue). Optional
-- late/on-time crosstab for context — not a second value axis.
-- =========================================================
WITH base AS (
    SELECT
        is_low_review,
        review_score,
        is_late_delivery,
        freight_revenue / NULLIF(item_revenue, 0) AS freight_ratio
    FROM mart_order_fact
    WHERE order_status = 'delivered'
      AND review_score IS NOT NULL
      AND item_revenue IS NOT NULL
      AND item_revenue > 0
      AND freight_revenue IS NOT NULL
),
with_tercile AS (
    SELECT
        *,
        NTILE(3) OVER (ORDER BY freight_ratio) AS freight_ratio_tercile
    FROM base
)
SELECT
    freight_ratio_tercile,
    CASE freight_ratio_tercile
        WHEN 1 THEN 'Low freight ratio'
        WHEN 2 THEN 'Mid freight ratio'
        WHEN 3 THEN 'High freight ratio'
    END AS freight_ratio_bucket,
    COUNT(*) AS orders,
    ROUND(AVG(freight_ratio), 3) AS avg_freight_ratio,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM with_tercile
GROUP BY freight_ratio_tercile
ORDER BY freight_ratio_tercile;


-- H6/H7 context: freight-ratio tercile × late/on-time
WITH base AS (
    SELECT
        is_low_review,
        review_score,
        is_late_delivery,
        freight_revenue / NULLIF(item_revenue, 0) AS freight_ratio
    FROM mart_order_fact
    WHERE order_status = 'delivered'
      AND review_score IS NOT NULL
      AND item_revenue IS NOT NULL
      AND item_revenue > 0
      AND freight_revenue IS NOT NULL
      AND is_late_delivery IS NOT NULL
),
with_tercile AS (
    SELECT
        *,
        NTILE(3) OVER (ORDER BY freight_ratio) AS freight_ratio_tercile
    FROM base
)
SELECT
    CASE freight_ratio_tercile
        WHEN 1 THEN 'Low freight ratio'
        WHEN 2 THEN 'Mid freight ratio'
        WHEN 3 THEN 'High freight ratio'
    END AS freight_ratio_bucket,
    CASE WHEN is_late_delivery = 1 THEN 'Late' ELSE 'On time or early' END AS delivery_status,
    COUNT(*) AS orders,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM with_tercile
GROUP BY freight_ratio_tercile, delivery_status
ORDER BY freight_ratio_tercile, delivery_status;


-- =========================================================
-- H8: Order complexity (item count / seller count)
-- =========================================================
SELECT
    CASE WHEN item_count > 1 THEN 'Multi-item' ELSE 'Single-item' END AS item_complexity,
    CASE WHEN seller_count > 1 THEN 'Multi-seller' ELSE 'Single-seller' END AS seller_complexity,
    COUNT(*) AS orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct,
    ROUND(100.0 * AVG(is_late_delivery), 2) AS late_delivery_rate_pct
FROM mart_order_fact
WHERE order_status = 'delivered'
  AND review_score IS NOT NULL
  AND item_count IS NOT NULL
  AND seller_count IS NOT NULL
GROUP BY item_complexity, seller_complexity
ORDER BY low_review_rate_pct DESC;


-- H8 stratified by on-time vs late
SELECT
    CASE WHEN item_count > 1 THEN 'Multi-item' ELSE 'Single-item' END AS item_complexity,
    CASE WHEN is_late_delivery = 1 THEN 'Late' ELSE 'On time or early' END AS delivery_status,
    COUNT(*) AS orders,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM mart_order_fact
WHERE order_status = 'delivered'
  AND review_score IS NOT NULL
  AND item_count IS NOT NULL
  AND is_late_delivery IS NOT NULL
GROUP BY item_complexity, delivery_status
ORDER BY item_complexity, delivery_status;


-- =========================================================
-- H9: Category low-review risk among ON-TIME deliveries only
-- Restricted to on-time deliveries to hold logistics roughly
-- constant and isolate category/product risk (not a repeat of H1).
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
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
      AND o.order_delivered_customer_date <= o.order_estimated_delivery_date
)
SELECT
    category,
    COUNT(*) AS items_in_on_time_reviewed_orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * AVG(is_low_review), 2) AS low_review_rate_pct
FROM item_reviews
GROUP BY category
HAVING COUNT(*) >= 100
ORDER BY low_review_rate_pct DESC, items_in_on_time_reviewed_orders DESC
LIMIT 15;


-- =========================================================
-- H12: Seller-level risk after controlling for late delivery
-- On-time low-review rate isolates seller/product quality
-- from logistics lateness.
-- =========================================================
WITH seller_metrics AS (
    SELECT
        oi.seller_id,
        COUNT(DISTINCT oi.order_id) AS delivered_orders,
        COUNT(DISTINCT CASE
            WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                THEN oi.order_id
        END) AS on_time_orders,
        AVG(r.review_score) AS avg_review_score,
        AVG(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) AS low_review_rate,
        AVG(
            CASE
                WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1
                ELSE 0
            END
        ) AS late_delivery_rate,
        AVG(
            CASE
                WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                     AND r.review_score <= 2 THEN 1
                WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                     AND r.review_score > 2 THEN 0
                ELSE NULL
            END
        ) AS on_time_low_review_rate
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
    on_time_orders,
    ROUND(avg_review_score, 2) AS avg_review_score,
    ROUND(100.0 * low_review_rate, 2) AS low_review_rate_pct,
    ROUND(100.0 * late_delivery_rate, 2) AS late_delivery_rate_pct,
    ROUND(100.0 * on_time_low_review_rate, 2) AS on_time_low_review_rate_pct
FROM seller_metrics
WHERE delivered_orders >= 50
  AND on_time_orders >= 30
ORDER BY on_time_low_review_rate DESC, late_delivery_rate DESC
LIMIT 20;


-- =========================================================
-- H10/H11: Retention timing after first customer experience
-- Expect a small effect — report carefully; do not overclaim.
-- =========================================================
WITH ranked_orders AS (
    SELECT
        customer_unique_id,
        order_id,
        order_purchase_timestamp,
        review_score,
        is_late_delivery,
        ROW_NUMBER() OVER (
            PARTITION BY customer_unique_id
            ORDER BY order_purchase_timestamp
        ) AS order_number,
        LEAD(order_id) OVER (
            PARTITION BY customer_unique_id
            ORDER BY order_purchase_timestamp
        ) AS next_order_id,
        LEAD(order_purchase_timestamp) OVER (
            PARTITION BY customer_unique_id
            ORDER BY order_purchase_timestamp
        ) AS next_order_purchase_timestamp
    FROM mart_order_fact
    WHERE order_status = 'delivered'
),
first_reviewed_orders AS (
    SELECT
        customer_unique_id,
        order_purchase_timestamp,
        review_score,
        is_late_delivery,
        next_order_id,
        CASE
            WHEN next_order_purchase_timestamp IS NOT NULL
                THEN DATEDIFF(next_order_purchase_timestamp, order_purchase_timestamp)
        END AS days_to_next_order
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
    ) AS repeat_purchase_rate_pct,
    ROUND(AVG(days_to_next_order), 1) AS avg_days_to_next_order,
    ROUND(
        AVG(CASE WHEN days_to_next_order IS NOT NULL THEN days_to_next_order END),
        1
    ) AS avg_days_to_next_order_among_repeaters
FROM first_reviewed_orders
GROUP BY first_order_review_group
ORDER BY CASE first_order_review_group
    WHEN 'Low review (1-2)' THEN 1
    WHEN 'Neutral review (3)' THEN 2
    WHEN 'High review (4-5)' THEN 3
END;


-- H11 context: first low review × first-order lateness
WITH ranked_orders AS (
    SELECT
        customer_unique_id,
        order_id,
        order_purchase_timestamp,
        review_score,
        is_late_delivery,
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
        review_score,
        is_late_delivery,
        next_order_id
    FROM ranked_orders
    WHERE order_number = 1
      AND review_score IS NOT NULL
      AND is_late_delivery IS NOT NULL
      AND order_purchase_timestamp < '2018-07-01'
)
SELECT
    CASE
        WHEN review_score <= 2 THEN 'Low review (1-2)'
        WHEN review_score = 3 THEN 'Neutral review (3)'
        WHEN review_score >= 4 THEN 'High review (4-5)'
    END AS first_order_review_group,
    CASE WHEN is_late_delivery = 1 THEN 'Late' ELSE 'On time or early' END AS first_order_delivery_status,
    COUNT(*) AS customers,
    ROUND(
        100.0 * SUM(CASE WHEN next_order_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS repeat_purchase_rate_pct
FROM first_reviewed_orders
GROUP BY first_order_review_group, first_order_delivery_status
ORDER BY first_order_review_group, first_order_delivery_status;
