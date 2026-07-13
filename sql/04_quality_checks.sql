USE olist_analytics;

-- Does the view have exactly one row per order?
SELECT
    COUNT(*) AS all_rows,
    COUNT(DISTINCT order_id) AS unique_orders,
    COUNT(*) - COUNT(DISTINCT order_id) AS duplicate_rows
FROM mart_order_fact;

-- What are the order statuses?
SELECT
    order_status,
    COUNT(*) AS orders
FROM mart_order_fact
GROUP BY order_status
ORDER BY orders DESC;

-- Missing data relevant to CX analysis
SELECT
    COUNT(*) AS all_orders,
    SUM(CASE WHEN review_score IS NULL THEN 1 ELSE 0 END) AS orders_without_review,
    SUM(CASE WHEN order_delivered_customer_date IS NULL THEN 1 ELSE 0 END) AS orders_without_delivery_date,
    SUM(CASE WHEN order_gmv IS NULL THEN 1 ELSE 0 END) AS orders_without_items
FROM mart_order_fact;

-- Unusual delivery time checks
SELECT
    MIN(delivery_days) AS min_delivery_days,
    MAX(delivery_days) AS max_delivery_days,
    MIN(delivery_delay_days) AS min_delivery_delay_days,
    MAX(delivery_delay_days) AS max_delivery_delay_days
FROM mart_order_fact
WHERE order_status = 'delivered';

-- Review score distribution
SELECT
    review_score,
    COUNT(*) AS orders
FROM mart_order_fact
WHERE review_score IS NOT NULL
GROUP BY review_score
ORDER BY review_score;