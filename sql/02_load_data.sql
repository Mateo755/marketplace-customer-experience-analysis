USE olist_analytics;

LOAD DATA LOCAL INFILE '/home/mateusz/VScode/marketplace-customer-experience-analysis/data/raw/olist_orders_dataset.csv'
INTO TABLE raw_orders
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(
    order_id,
    customer_id,
    order_status,
    @order_purchase_timestamp,
    @order_approved_at,
    @order_delivered_carrier_date,
    @order_delivered_customer_date,
    @order_estimated_delivery_date
)
SET
    order_purchase_timestamp = NULLIF(@order_purchase_timestamp, ''),
    order_delivered_customer_date = NULLIF(@order_delivered_customer_date, ''),
    order_estimated_delivery_date = NULLIF(@order_estimated_delivery_date, '');

LOAD DATA LOCAL INFILE '/home/mateusz/VScode/marketplace-customer-experience-analysis/data/raw/olist_order_items_dataset.csv'
INTO TABLE raw_order_items
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(
    order_id,
    order_item_id,
    product_id,
    seller_id,
    @shipping_limit_date,
    price,
    freight_value
)
SET
    shipping_limit_date = NULLIF(@shipping_limit_date, '');

LOAD DATA LOCAL INFILE '/home/mateusz/VScode/marketplace-customer-experience-analysis/data/raw/olist_order_reviews_dataset.csv'
INTO TABLE raw_order_reviews
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(
    review_id,
    order_id,
    review_score,
    @review_comment_title,
    @review_comment_message,
    @review_creation_date,
    @review_answer_timestamp
)
SET
    review_creation_date = NULLIF(@review_creation_date, ''),
    review_answer_timestamp = NULLIF(@review_answer_timestamp, '');

LOAD DATA LOCAL INFILE '/home/mateusz/VScode/marketplace-customer-experience-analysis/data/raw/olist_customers_dataset.csv'
INTO TABLE raw_customers
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE '/home/mateusz/VScode/marketplace-customer-experience-analysis/data/raw/olist_products_dataset.csv'
INTO TABLE raw_products
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE '/home/mateusz/VScode/marketplace-customer-experience-analysis/data/raw/product_category_name_translation.csv'
INTO TABLE raw_category_translation
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;