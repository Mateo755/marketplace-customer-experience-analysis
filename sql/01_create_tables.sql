USE olist_analytics;

DROP TABLE IF EXISTS raw_category_translation;
DROP TABLE IF EXISTS raw_products;
DROP TABLE IF EXISTS raw_customers;
DROP TABLE IF EXISTS raw_order_reviews;
DROP TABLE IF EXISTS raw_order_items;
DROP TABLE IF EXISTS raw_orders;

CREATE TABLE raw_orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL,
    order_status VARCHAR(30),
    order_purchase_timestamp DATETIME,
    order_delivered_customer_date DATETIME,
    order_estimated_delivery_date DATETIME
);

CREATE TABLE raw_order_items (
    order_id VARCHAR(50) NOT NULL,
    order_item_id INT NOT NULL,
    product_id VARCHAR(50),
    seller_id VARCHAR(50),
    shipping_limit_date DATETIME,
    price DECIMAL(12, 2),
    freight_value DECIMAL(12, 2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE raw_order_reviews (
    review_id VARCHAR(50),
    order_id VARCHAR(50),
    review_score INT,
    review_creation_date DATETIME,
    review_answer_timestamp DATETIME,
    INDEX idx_reviews_order_id (order_id)
);

CREATE TABLE raw_customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_unique_id VARCHAR(50) NOT NULL,
    customer_zip_code_prefix INT,
    customer_city VARCHAR(100),
    customer_state VARCHAR(10),
    INDEX idx_customers_unique_id (customer_unique_id)
);

CREATE TABLE raw_products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_category_name VARCHAR(100),
    product_name_lenght INT,
    product_description_lenght INT,
    product_photos_qty INT,
    product_weight_g INT,
    product_length_cm INT,
    product_height_cm INT,
    product_width_cm INT
);

CREATE TABLE raw_category_translation (
    product_category_name VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100)
);