#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yajus_kitchen.settings')
django.setup()

from django.core.management import call_command
from django.db import connection, OperationalError, ProgrammingError
from django.contrib.auth.models import User
from kitchen.models import Category, FoodItem

print("Starting migrations...")

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def table_exists(cursor, table_name):
    cursor.execute("SHOW TABLES LIKE %s", [table_name])
    return cursor.fetchone() is not None


def column_exists(cursor, table_name, column_name):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        [table_name, column_name]
    )
    return cursor.fetchone()[0] > 0


def index_exists(cursor, table_name, index_name):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s",
        [table_name, index_name]
    )
    return cursor.fetchone()[0] > 0


# ---------------------------------------------------------------------------
# Step 1 – Create any missing tables & add any missing columns
# ---------------------------------------------------------------------------
print("Checking for missing tables and columns...")
try:
    with connection.cursor() as cursor:

        # --- kitchen_category ---
        if not table_exists(cursor, 'kitchen_category'):
            print("Creating kitchen_category...")
            cursor.execute("""
                CREATE TABLE kitchen_category (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE
                )
            """)

        # --- kitchen_optiongroup ---
        if not table_exists(cursor, 'kitchen_optiongroup'):
            print("Creating kitchen_optiongroup...")
            cursor.execute("""
                CREATE TABLE kitchen_optiongroup (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL
                )
            """)

        # --- kitchen_optionchoice ---
        if not table_exists(cursor, 'kitchen_optionchoice'):
            print("Creating kitchen_optionchoice...")
            cursor.execute("""
                CREATE TABLE kitchen_optionchoice (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    group_id BIGINT NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    price_delta DECIMAL(8,2) DEFAULT 0.00,
                    FOREIGN KEY (group_id) REFERENCES kitchen_optiongroup(id)
                )
            """)
        else:
            # Patch: add group_id if it is missing (common cause of OperationalError on existing DBs)
            if not column_exists(cursor, 'kitchen_optionchoice', 'group_id'):
                print("Adding missing column kitchen_optionchoice.group_id ...")
                cursor.execute("""
                    ALTER TABLE kitchen_optionchoice
                    ADD COLUMN group_id BIGINT NOT NULL DEFAULT 0
                """)
                # Add FK only after column exists
                try:
                    cursor.execute("""
                        ALTER TABLE kitchen_optionchoice
                        ADD CONSTRAINT fk_optionchoice_group
                        FOREIGN KEY (group_id) REFERENCES kitchen_optiongroup(id)
                    """)
                except Exception as fk_err:
                    print(f"  FK warning (non-fatal): {fk_err}")
            if not column_exists(cursor, 'kitchen_optionchoice', 'price_delta'):
                print("Adding missing column kitchen_optionchoice.price_delta ...")
                cursor.execute("""
                    ALTER TABLE kitchen_optionchoice
                    ADD COLUMN price_delta DECIMAL(8,2) NOT NULL DEFAULT 0.00
                """)

        # --- kitchen_fooditem ---
        if not table_exists(cursor, 'kitchen_fooditem'):
            print("Creating kitchen_fooditem...")
            cursor.execute("""
                CREATE TABLE kitchen_fooditem (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    category_id BIGINT NOT NULL,
                    description TEXT NOT NULL,
                    base_price DECIMAL(10,2) NOT NULL,
                    image VARCHAR(100),
                    is_available BOOLEAN DEFAULT TRUE,
                    INDEX (name),
                    INDEX (category_id),
                    INDEX (is_available),
                    FOREIGN KEY (category_id) REFERENCES kitchen_category(id)
                )
            """)
        else:
            for col, defn in [
                ('description', 'TEXT NOT NULL DEFAULT ""'),
                ('base_price', 'DECIMAL(10,2) NOT NULL DEFAULT 0.00'),
                ('image', 'VARCHAR(100)'),
                ('is_available', 'BOOLEAN DEFAULT TRUE'),
                ('category_id', 'BIGINT NOT NULL DEFAULT 0'),
            ]:
                if not column_exists(cursor, 'kitchen_fooditem', col):
                    print(f"Adding missing column kitchen_fooditem.{col} ...")
                    cursor.execute(f"ALTER TABLE kitchen_fooditem ADD COLUMN {col} {defn}")
            # Ensure indexes
            for idx, col in [
                ('kitchen_foo_name_91083f_idx', 'name'),
                ('kitchen_foo_categor_28d06b_idx', 'category_id'),
                ('kitchen_foo_is_avai_5aabd9_idx', 'is_available'),
            ]:
                if not index_exists(cursor, 'kitchen_fooditem', idx):
                    try:
                        cursor.execute(f"CREATE INDEX {idx} ON kitchen_fooditem({col})")
                    except Exception as idx_err:
                        print(f"  Index warning (non-fatal): {idx_err}")

        # --- kitchen_fooditemoption ---
        if not table_exists(cursor, 'kitchen_fooditemoption'):
            print("Creating kitchen_fooditemoption...")
            cursor.execute("""
                CREATE TABLE kitchen_fooditemoption (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    food_id BIGINT NOT NULL,
                    group_id BIGINT NOT NULL,
                    UNIQUE KEY (food_id, group_id),
                    FOREIGN KEY (food_id) REFERENCES kitchen_fooditem(id),
                    FOREIGN KEY (group_id) REFERENCES kitchen_optiongroup(id)
                )
            """)

        # --- kitchen_cart ---
        if not table_exists(cursor, 'kitchen_cart'):
            print("Creating kitchen_cart...")
            cursor.execute("""
                CREATE TABLE kitchen_cart (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNIQUE,
                    session_key VARCHAR(40),
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    INDEX (session_key),
                    FOREIGN KEY (user_id) REFERENCES auth_user(id)
                )
            """)
        else:
            if not column_exists(cursor, 'kitchen_cart', 'session_key'):
                print("Adding missing column kitchen_cart.session_key ...")
                cursor.execute("ALTER TABLE kitchen_cart ADD COLUMN session_key VARCHAR(40)")
            if not column_exists(cursor, 'kitchen_cart', 'updated_at'):
                print("Adding missing column kitchen_cart.updated_at ...")
                cursor.execute("ALTER TABLE kitchen_cart ADD COLUMN updated_at DATETIME NOT NULL DEFAULT NOW()")

        # --- kitchen_cartitem ---
        if not table_exists(cursor, 'kitchen_cartitem'):
            print("Creating kitchen_cartitem...")
            cursor.execute("""
                CREATE TABLE kitchen_cartitem (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    cart_id BIGINT NOT NULL,
                    food_id BIGINT NOT NULL,
                    quantity INT UNSIGNED DEFAULT 1,
                    added_at DATETIME NOT NULL,
                    FOREIGN KEY (cart_id) REFERENCES kitchen_cart(id),
                    FOREIGN KEY (food_id) REFERENCES kitchen_fooditem(id)
                )
            """)

        # --- kitchen_cartitem_selected_options ---
        if not table_exists(cursor, 'kitchen_cartitem_selected_options'):
            print("Creating kitchen_cartitem_selected_options...")
            cursor.execute("""
                CREATE TABLE kitchen_cartitem_selected_options (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    cartitem_id BIGINT NOT NULL,
                    optionchoice_id BIGINT NOT NULL,
                    UNIQUE KEY (cartitem_id, optionchoice_id),
                    FOREIGN KEY (cartitem_id) REFERENCES kitchen_cartitem(id),
                    FOREIGN KEY (optionchoice_id) REFERENCES kitchen_optionchoice(id)
                )
            """)

        # --- kitchen_order ---
        if not table_exists(cursor, 'kitchen_order'):
            print("Creating kitchen_order...")
            cursor.execute("""
                CREATE TABLE kitchen_order (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT,
                    guest_name VARCHAR(100) DEFAULT '',
                    guest_email VARCHAR(254) DEFAULT '',
                    guest_phone VARCHAR(20) DEFAULT '',
                    order_number VARCHAR(20) UNIQUE,
                    total_amount DECIMAL(10,2) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    delivery_address TEXT,
                    special_instructions TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES auth_user(id)
                )
            """)
        else:
            for col, defn in [
                ('guest_name', "VARCHAR(100) NOT NULL DEFAULT ''"),
                ('guest_email', "VARCHAR(254) NOT NULL DEFAULT ''"),
                ('guest_phone', "VARCHAR(20) NOT NULL DEFAULT ''"),
                ('order_number', 'VARCHAR(20) UNIQUE'),
                ('delivery_address', 'TEXT'),
                ('special_instructions', 'TEXT'),
                ('updated_at', 'DATETIME NOT NULL DEFAULT NOW()'),
            ]:
                if not column_exists(cursor, 'kitchen_order', col):
                    print(f"Adding missing column kitchen_order.{col} ...")
                    cursor.execute(f"ALTER TABLE kitchen_order ADD COLUMN {col} {defn}")

        # --- kitchen_orderitem ---
        if not table_exists(cursor, 'kitchen_orderitem'):
            print("Creating kitchen_orderitem...")
            cursor.execute("""
                CREATE TABLE kitchen_orderitem (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    order_id BIGINT NOT NULL,
                    food_id BIGINT,
                    food_name VARCHAR(150) NOT NULL,
                    food_price DECIMAL(10,2) NOT NULL,
                    quantity INT UNSIGNED NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES kitchen_order(id),
                    FOREIGN KEY (food_id) REFERENCES kitchen_fooditem(id)
                )
            """)
        else:
            for col, defn in [
                ('food_name', "VARCHAR(150) NOT NULL DEFAULT ''"),
                ('food_price', 'DECIMAL(10,2) NOT NULL DEFAULT 0.00'),
            ]:
                if not column_exists(cursor, 'kitchen_orderitem', col):
                    print(f"Adding missing column kitchen_orderitem.{col} ...")
                    cursor.execute(f"ALTER TABLE kitchen_orderitem ADD COLUMN {col} {defn}")

        # --- kitchen_orderitem_selected_options ---
        if not table_exists(cursor, 'kitchen_orderitem_selected_options'):
            print("Creating kitchen_orderitem_selected_options...")
            cursor.execute("""
                CREATE TABLE kitchen_orderitem_selected_options (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    orderitem_id BIGINT NOT NULL,
                    optionchoice_id BIGINT NOT NULL,
                    UNIQUE KEY (orderitem_id, optionchoice_id),
                    FOREIGN KEY (orderitem_id) REFERENCES kitchen_orderitem(id),
                    FOREIGN KEY (optionchoice_id) REFERENCES kitchen_optionchoice(id)
                )
            """)

        # --- kitchen_payment ---
        if not table_exists(cursor, 'kitchen_payment'):
            print("Creating kitchen_payment...")
            cursor.execute("""
                CREATE TABLE kitchen_payment (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    order_id BIGINT NOT NULL UNIQUE,
                    reference VARCHAR(100) NOT NULL UNIQUE,
                    amount DECIMAL(10,2) NOT NULL,
                    method VARCHAR(20) DEFAULT 'paystack',
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES kitchen_order(id)
                )
            """)

        # --- kitchen_review ---
        if not table_exists(cursor, 'kitchen_review'):
            print("Creating kitchen_review...")
            cursor.execute("""
                CREATE TABLE kitchen_review (
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
            """)

        # --- django_session (needed for guest cart) ---
        if not table_exists(cursor, 'django_session'):
            print("Creating django_session...")
            cursor.execute("""
                CREATE TABLE django_session (
                    session_key VARCHAR(40) NOT NULL PRIMARY KEY,
                    session_data LONGTEXT NOT NULL,
                    expire_date DATETIME(6) NOT NULL,
                    INDEX django_session_expire_date_a5c62663 (expire_date)
                )
            """)

        print("All table checks and repairs complete.")

except (OperationalError, ProgrammingError) as e:
    print(f"Warning while checking/creating tables: {e}")
    print("Continuing...")
except Exception as e:
    print(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Step 2 – Fake the initial migration then run any remaining migrations
# ---------------------------------------------------------------------------
print("Now handling Django migrations...")
try:
    call_command('migrate', '--fake', 'kitchen', '0001')
    print("Faked kitchen 0001 initial migration!")
except Exception as e:
    print(f"Fake migration failed (might already be applied): {e}")

try:
    call_command('migrate', '--run-syncdb')
    print("All migrations completed!")
except Exception as e:
    print(f"Final migrate failed: {e}")


# ---------------------------------------------------------------------------
# Step 3 – Seed data
# ---------------------------------------------------------------------------
print("Seeding database...")
try:
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@yajuskitchen.com', 'adminpassword123')
        print("Created superuser: admin")
    else:
        print("Superuser admin already exists")

    categories_data = ['Rice', 'Soups', 'Swallow', 'Grills', 'Drinks', 'Desserts']
    categories = {}
    for name in categories_data:
        cat, created = Category.objects.get_or_create(name=name)
        categories[name] = cat
        if created:
            print(f"Created category: {name}")

    foods = [
        {'name': 'Smoky Party Jollof Rice', 'category': 'Rice', 'description': 'Premium smokey Jollof served with sweet fried plantain and salad.', 'base_price': 3500.00},
        {'name': 'Special Fried Rice', 'category': 'Rice', 'description': 'Deliciously stir-fried rice loaded with fresh vegetables and eggs.', 'base_price': 3800.00},
        {'name': 'Efo Riro Native Soup', 'category': 'Soups', 'description': 'Rich Yoruba spinach soup stewed in palm oil, iru, and stock fish.', 'base_price': 4500.00},
        {'name': 'Egusi Soup', 'category': 'Soups', 'description': 'Traditional Nigerian melon seed soup enriched with pumpkin leaves.', 'base_price': 4200.00},
        {'name': 'Premium Pounded Yam', 'category': 'Swallow', 'description': 'Smooth, fluffy, and stretchy pounded yam. Best paired with Efo Riro.', 'base_price': 1000.00},
        {'name': 'Oat Swallow', 'category': 'Swallow', 'description': 'Healthy whole-grain swallow option high in fiber.', 'base_price': 1200.00},
        {'name': 'Spiced Suya Platter', 'category': 'Grills', 'description': 'Thinly sliced grilled beef skewers coated with spicy yaji pepper.', 'base_price': 5000.00},
        {'name': 'Yaju Signature Chapman', 'category': 'Drinks', 'description': 'Refreshing Nigerian classic mocktail with soft drinks and angostura bitters.', 'base_price': 1500.00},
        {'name': 'Sweet Golden Puff Puff', 'category': 'Desserts', 'description': 'Portion of 6 sweet, pillowy soft fried dough balls.', 'base_price': 800.00},
    ]

    for f_data in foods:
        food, created = FoodItem.objects.get_or_create(
            name=f_data['name'],
            defaults={
                'category': categories[f_data['category']],
                'description': f_data['description'],
                'base_price': f_data['base_price'],
                'is_available': True
            }
        )
        if not food.is_available:
            food.is_available = True
            food.save()
        if created:
            print(f"Created food item: {food.name}")
    print("Seeding completed!")
except Exception as e:
    print(f"Seeding error: {e}")
