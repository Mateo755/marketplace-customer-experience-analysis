USE olist_analytics;

DROP VIEW IF EXISTS mart_order_fact;

CREATE VIEW mart_order_fact AS
WITH item_agg AS (
    SELECT
        order_id,
        COUNT(*) AS item_count,
        COUNT(DISTINCT seller_id) AS seller_count,
        SUM(price) AS item_revenue,
        SUM(freight_value) AS freight_revenue,
        SUM(price + freight_value) AS order_gmv
    FROM raw_order_items
    GROUP BY order_id
),

category_agg AS (
    SELECT
        oi.order_id,
        GROUP_CONCAT(
            DISTINCT COALESCE(
                ct.product_category_name_english,
                p.product_category_name,
                'unknown'
            )
            ORDER BY COALESCE(
                ct.product_category_name_english,
                p.product_category_name,
                'unknown'
            )
            SEPARATOR ', '
        ) AS categories
    FROM raw_order_items oi
    LEFT JOIN raw_products p
        ON oi.product_id = p.product_id
    LEFT JOIN raw_category_translation ct
        ON p.product_category_name = ct.product_category_name
    GROUP BY oi.order_id
),

review_agg AS (
    SELECT
        order_id,
        AVG(review_score) AS review_score
    FROM raw_order_reviews
    GROUP BY order_id
)

SELECT
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,

    ia.item_count,
    ia.seller_count,
    ia.item_revenue,
    ia.freight_revenue,
    ia.order_gmv,

    ca.categories,
    ra.review_score,

    DATEDIFF(
        o.order_delivered_customer_date,
        o.order_purchase_timestamp
    ) AS delivery_days,

    DATEDIFF(
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date
    ) AS delivery_delay_days,

    CASE
        WHEN o.order_delivered_customer_date IS NULL THEN NULL
        WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
            THEN 1
        ELSE 0
    END AS is_late_delivery,

    CASE
        WHEN ra.review_score IS NULL THEN NULL
        WHEN ra.review_score <= 2 THEN 1
        ELSE 0
    END AS is_low_review

FROM raw_orders o
INNER JOIN raw_customers c
    ON o.customer_id = c.customer_id
LEFT JOIN item_agg ia
    ON o.order_id = ia.order_id
LEFT JOIN category_agg ca
    ON o.order_id = ca.order_id
LEFT JOIN review_agg ra
    ON o.order_id = ra.order_id;