#!/usr/bin/env python3
import mysql.connector
from getpass import getpass

# Get your TiDB credentials from environment variables or prompt!
TIDB_HOST = input("Enter TiDB host (e.g., xxx.aws.tidbcloud.com): ") or os.getenv("TIDB_HOST", "")
TIDB_PORT = int(input("Enter TiDB port (default 4000): ") or os.getenv("TIDB_PORT", "4000"))
TIDB_USER = input("Enter TiDB username: ") or os.getenv("TIDB_USER", "")
TIDB_PASSWORD = getpass("Enter TiDB password: ") or os.getenv("TIDB_PASSWORD", "")
TIDB_DATABASE = input("Enter TiDB database name (e.g., yajus_kitchen): ") or os.getenv("TIDB_DATABASE", "yajus_kitchen")

# Connect!
cnx = mysql.connector.connect(
    host=TIDB_HOST,
    port=TIDB_PORT,
    user=TIDB_USER,
    password=TIDB_PASSWORD,
    database=TIDB_DATABASE,
    ssl_ca='/etc/ssl/cert.pem'
)

cursor = cnx.cursor()

SQL_STATEMENTS = [
    # Create category table
    """
    CREATE TABLE IF NOT EXISTS kitchen_category (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE
    )
    """,
    # Option group table
    """
    CREATE TABLE IF NOT EXISTS kitchen_optiongroup (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL
    )
    """,
    # Option choice table
    """
    CREATE TABLE IF NOT EXISTS kitchen_optionchoice (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        group_id BIGINT NOT NULL,
        name VARCHAR(100) NOT NULL,
        price_delta DECIMAL(8,2) DEFAULT 0.00,
        FOREIGN KEY (group_id) REFERENCES kitchen_optiongroup(id)
    )
    """,
    # Food item table (add indexes after)
    """
    CREATE TABLE IF NOT EXISTS kitchen_fooditem (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(150) NOT NULL,
        category_id BIGINT NOT NULL,
        description TEXT NOT NULL,
        base_price DECIMAL(10,2) NOT NULL,
        image VARCHAR(100),
        is_available BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (category_id) REFERENCES kitchen_category(id)
    )
    """,
    # Add indexes to fooditem
    "CREATE INDEX IF NOT EXISTS kitchen_foo_name_91083f_idx ON kitchen_fooditem(name)",
    "CREATE INDEX IF NOT EXISTS kitchen_foo_categor_28d06b_idx ON kitchen_fooditem(category_id)",
    "CREATE INDEX IF NOT EXISTS kitchen_foo_is_avai_5aabd9_idx ON kitchen_fooditem(is_available)",
    # Food item option junction table
    """
    CREATE TABLE IF NOT EXISTS kitchen_fooditemoption (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        food_id BIGINT NOT NULL,
        group_id BIGINT NOT NULL,
        UNIQUE KEY (food_id, group_id),
        FOREIGN KEY (food_id) REFERENCES kitchen_fooditem(id),
        FOREIGN KEY (group_id) REFERENCES kitchen_optiongroup(id)
    )
    """,
    # Cart table
    """
    CREATE TABLE IF NOT EXISTS kitchen_cart (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT,
        session_key VARCHAR(40),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY (user_id),
        FOREIGN KEY (user_id) REFERENCES auth_user(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS kitchen_cart_session_key ON kitchen_cart(session_key)",
    # Cart item table
    """
    CREATE TABLE IF NOT EXISTS kitchen_cartitem (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        cart_id BIGINT NOT NULL,
        food_id BIGINT NOT NULL,
        quantity INT UNSIGNED DEFAULT 1,
        added_at DATETIME NOT NULL,
        FOREIGN KEY (cart_id) REFERENCES kitchen_cart(id),
        FOREIGN KEY (food_id) REFERENCES kitchen_fooditem(id)
    )
    """,
    # Cart item selected options junction table
    """
    CREATE TABLE IF NOT EXISTS kitchen_cartitem_selected_options (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        cartitem_id BIGINT NOT NULL,
        optionchoice_id BIGINT NOT NULL,
        UNIQUE KEY (cartitem_id, optionchoice_id),
        FOREIGN KEY (cartitem_id) REFERENCES kitchen_cartitem(id),
        FOREIGN KEY (optionchoice_id) REFERENCES kitchen_optionchoice(id)
    )
    """,
    # Order table
    """
    CREATE TABLE IF NOT EXISTS kitchen_order (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT,
        guest_name VARCHAR(100),
        guest_email VARCHAR(254),
        guest_phone VARCHAR(20),
        order_number VARCHAR(20),
        total_amount DECIMAL(10,2) NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        delivery_address TEXT,
        special_instructions TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        UNIQUE KEY (order_number),
        FOREIGN KEY (user_id) REFERENCES auth_user(id)
    )
    """,
    # Order item table
    """
    CREATE TABLE IF NOT EXISTS kitchen_orderitem (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        order_id BIGINT NOT NULL,
        food_id BIGINT,
        food_name VARCHAR(150) NOT NULL,
        food_price DECIMAL(10,2) NOT NULL,
        quantity INT UNSIGNED NOT NULL,
        FOREIGN KEY (order_id) REFERENCES kitchen_order(id),
        FOREIGN KEY (food_id) REFERENCES kitchen_fooditem(id)
    )
    """,
    # Order item selected options junction table
    """
    CREATE TABLE IF NOT EXISTS kitchen_orderitem_selected_options (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        orderitem_id BIGINT NOT NULL,
        optionchoice_id BIGINT NOT NULL,
        UNIQUE KEY (orderitem_id, optionchoice_id),
        FOREIGN KEY (orderitem_id) REFERENCES kitchen_orderitem(id),
        FOREIGN KEY (optionchoice_id) REFERENCES kitchen_optionchoice(id)
    )
    """,
    # Payment table
    """
    CREATE TABLE IF NOT EXISTS kitchen_payment (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        order_id BIGINT NOT NULL UNIQUE,
        reference VARCHAR(100) NOT NULL UNIQUE,
        amount DECIMAL(10,2) NOT NULL,
        method VARCHAR(20) DEFAULT 'paystack',
        status VARCHAR(20) DEFAULT 'pending',
        created_at DATETIME NOT NULL,
        FOREIGN KEY (order_id) REFERENCES kitchen_order(id)
    )
    """,
    # Review table
    """
    CREATE TABLE IF NOT EXISTS kitchen_review (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        food_id BIGINT NOT NULL,
        rating INT UNSIGNED NOT NULL,
        comment TEXT,
        created_at DATETIME NOT NULL,
        UNIQUE KEY (user_id, food_id),
        FOREIGN KEY (user_id) REFERENCES auth_user(id),
        FOREIGN KEY (food_id) REFERENCES kitchen_fooditem(id)
    )
    """
]

print("Connected! Creating tables...")
for i, sql in enumerate(SQL_STATEMENTS):
    try:
        print(f"Running {i+1}/{len(SQL_STATEMENTS)}...")
        cursor.execute(sql)
        cnx.commit()
    except Exception as e:
        print(f"Warning on statement {i+1}: {e} (might already exist)")

print("All tables created!")
cursor.close()
cnx.close()
