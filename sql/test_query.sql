SHOW TABLES;


SHOW GLOBAL VARIABLES LIKE 'local_infile';
SET GLOBAL local_infile = 1;
# Important, for server side you also need to changed that in options


USE olist_analytics;

SELECT 'orders' AS table_name, COUNT(*) AS row_count FROM raw_orders
UNION ALL
SELECT 'order_items', COUNT(*) FROM raw_order_items
UNION ALL
SELECT 'reviews', COUNT(*) FROM raw_order_reviews
UNION ALL
SELECT 'customers', COUNT(*) FROM raw_customers
UNION ALL
SELECT 'products', COUNT(*) FROM raw_products
UNION ALL
SELECT 'category_translation', COUNT(*) FROM raw_category_translation;

SELECT * FROM raw_orders LIMIT 5;
SELECT * FROM raw_order_items LIMIT 5;
SELECT * FROM raw_order_reviews LIMIT 5;