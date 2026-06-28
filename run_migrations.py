#!/usr/bin/env python
"""
Render build script: runs Django migrations, then seeds initial data.
Migration 0001 is faked (tables created by prior raw SQL or existing DB).
Migration 0002 applies the ALTER TABLE repairs using IF NOT EXISTS.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yajus_kitchen.settings')
django.setup()

from django.core.management import call_command
from django.db import connection, OperationalError, ProgrammingError
from django.contrib.auth.models import User

print("=" * 60)
print("YAJU'S KITCHEN — RENDER BUILD MIGRATION SCRIPT")
print("=" * 60)


# ---------------------------------------------------------------------------
# Step 1: Ensure all base tables exist via raw SQL (safe, CREATE IF NOT EXISTS)
# ---------------------------------------------------------------------------
print("\n[1/3] Ensuring base tables exist...")

BASE_TABLES_SQL = [
    ("auth_user check", None),   # placeholder — Django handles auth tables
    ("kitchen_category", """
        CREATE TABLE IF NOT EXISTS kitchen_category (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE
        )
    """),
    ("kitchen_optiongroup", """
        CREATE TABLE IF NOT EXISTS kitchen_optiongroup (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL
        )
    """),
    ("kitchen_optionchoice", """
        CREATE TABLE IF NOT EXISTS kitchen_optionchoice (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            group_id BIGINT NOT NULL DEFAULT 0,
            name VARCHAR(100) NOT NULL,
            price_delta DECIMAL(8,2) NOT NULL DEFAULT 0.00
        )
    """),
    ("kitchen_fooditem", """
        CREATE TABLE IF NOT EXISTS kitchen_fooditem (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            category_id BIGINT NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            base_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            image VARCHAR(100),
            is_available BOOLEAN DEFAULT TRUE
        )
    """),
    ("kitchen_fooditemoption", """
        CREATE TABLE IF NOT EXISTS kitchen_fooditemoption (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            food_id BIGINT NOT NULL DEFAULT 0,
            group_id BIGINT NOT NULL DEFAULT 0
        )
    """),
    ("kitchen_cart", """
        CREATE TABLE IF NOT EXISTS kitchen_cart (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT UNIQUE,
            session_key VARCHAR(40),
            created_at DATETIME NOT NULL DEFAULT NOW(),
            updated_at DATETIME NOT NULL DEFAULT NOW()
        )
    """),
    ("kitchen_cartitem", """
        CREATE TABLE IF NOT EXISTS kitchen_cartitem (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            cart_id BIGINT NOT NULL DEFAULT 0,
            food_id BIGINT NOT NULL DEFAULT 0,
            quantity INT UNSIGNED DEFAULT 1,
            added_at DATETIME NOT NULL DEFAULT NOW()
        )
    """),
    ("kitchen_cartitem_selected_options", """
        CREATE TABLE IF NOT EXISTS kitchen_cartitem_selected_options (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            cartitem_id BIGINT NOT NULL DEFAULT 0,
            optionchoice_id BIGINT NOT NULL DEFAULT 0
        )
    """),
    ("kitchen_order", """
        CREATE TABLE IF NOT EXISTS kitchen_order (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            guest_name VARCHAR(100) NOT NULL DEFAULT '',
            guest_email VARCHAR(254) NOT NULL DEFAULT '',
            guest_phone VARCHAR(20) NOT NULL DEFAULT '',
            order_number VARCHAR(20) UNIQUE,
            total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            status VARCHAR(20) DEFAULT 'pending',
            delivery_address TEXT,
            special_instructions TEXT,
            created_at DATETIME NOT NULL DEFAULT NOW(),
            updated_at DATETIME NOT NULL DEFAULT NOW()
        )
    """),
    ("kitchen_orderitem", """
        CREATE TABLE IF NOT EXISTS kitchen_orderitem (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            order_id BIGINT NOT NULL DEFAULT 0,
            food_id BIGINT,
            food_name VARCHAR(150) NOT NULL DEFAULT '',
            food_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            quantity INT UNSIGNED NOT NULL DEFAULT 1
        )
    """),
    ("kitchen_orderitem_selected_options", """
        CREATE TABLE IF NOT EXISTS kitchen_orderitem_selected_options (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            orderitem_id BIGINT NOT NULL DEFAULT 0,
            optionchoice_id BIGINT NOT NULL DEFAULT 0
        )
    """),
    ("kitchen_payment", """
        CREATE TABLE IF NOT EXISTS kitchen_payment (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            order_id BIGINT NOT NULL UNIQUE DEFAULT 0,
            reference VARCHAR(100) NOT NULL UNIQUE,
            amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            method VARCHAR(20) DEFAULT 'paystack',
            status VARCHAR(20) DEFAULT 'pending',
            created_at DATETIME NOT NULL DEFAULT NOW()
        )
    """),
    ("kitchen_review", """
        CREATE TABLE IF NOT EXISTS kitchen_review (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL DEFAULT 0,
            food_id BIGINT NOT NULL DEFAULT 0,
            rating INT UNSIGNED NOT NULL DEFAULT 1,
            comment TEXT,
            created_at DATETIME NOT NULL DEFAULT NOW()
        )
    """),
    ("django_session", """
        CREATE TABLE IF NOT EXISTS django_session (
            session_key VARCHAR(40) NOT NULL PRIMARY KEY,
            session_data LONGTEXT NOT NULL,
            expire_date DATETIME(6) NOT NULL
        )
    """),
]

try:
    with connection.cursor() as cursor:
        for label, sql in BASE_TABLES_SQL:
            if sql is None:
                continue
            try:
                cursor.execute(sql)
                print(f"  ✓ {label}")
            except Exception as e:
                print(f"  ! {label} — {e}")
except Exception as e:
    print(f"  DB connection error: {e}")
    sys.exit(1)

print("  Base table check complete.")


# ---------------------------------------------------------------------------
# Step 2: Django migrations
#   - Fake 0001 (already handled by raw SQL above)
#   - Run 0002 which does the ALTER TABLE IF NOT EXISTS repairs
#   - Run --run-syncdb for auth/admin/session tables
# ---------------------------------------------------------------------------
print("\n[2/3] Running Django migrations...")

# Fake initial migration (tables already exist)
try:
    call_command('migrate', '--fake', 'kitchen', '0001', verbosity=1)
    print("  ✓ Faked kitchen 0001_initial")
except Exception as e:
    print(f"  ! Fake 0001 (may already be applied): {e}")

# Apply schema repair migration (0002) — this does the ALTER TABLE fixes
try:
    call_command('migrate', 'kitchen', verbosity=1)
    print("  ✓ Applied remaining kitchen migrations (0002+)")
except Exception as e:
    print(f"  ! kitchen migrations failed: {e}")

# Apply auth/admin/contenttypes/session migrations
try:
    call_command('migrate', '--run-syncdb', verbosity=1)
    print("  ✓ Applied all framework migrations")
except Exception as e:
    print(f"  ! Framework migrations failed: {e}")

print("  Migrations complete.")


# ---------------------------------------------------------------------------
# Step 3: Seed initial data
# ---------------------------------------------------------------------------
print("\n[3/3] Seeding initial data...")

try:
    from kitchen.models import Category, FoodItem

    # Superuser
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@yajuskitchen.com', 'adminpassword123')
        print("  ✓ Created superuser: admin")
    else:
        print("  - Superuser already exists")

    # Categories
    category_names = ['Rice', 'Soups', 'Swallow', 'Grills', 'Drinks', 'Desserts']
    categories = {}
    for name in category_names:
        cat, created = Category.objects.get_or_create(name=name)
        categories[name] = cat
        if created:
            print(f"  ✓ Created category: {name}")

    # Food items
    foods = [
        ('Smoky Party Jollof Rice',    'Rice',     'Premium smokey Jollof served with sweet fried plantain and salad.', 3500.00),
        ('Special Fried Rice',         'Rice',     'Deliciously stir-fried rice loaded with fresh vegetables and eggs.', 3800.00),
        ('Efo Riro Native Soup',       'Soups',    'Rich Yoruba spinach soup stewed in palm oil, iru, and stock fish.', 4500.00),
        ('Egusi Soup',                 'Soups',    'Traditional Nigerian melon seed soup enriched with pumpkin leaves.', 4200.00),
        ('Premium Pounded Yam',        'Swallow',  'Smooth, fluffy pounded yam — best paired with Efo Riro.', 1000.00),
        ('Oat Swallow',                'Swallow',  'Healthy whole-grain swallow option high in fiber.', 1200.00),
        ('Spiced Suya Platter',        'Grills',   'Grilled beef skewers coated with spicy yaji pepper.', 5000.00),
        ('Yaju Signature Chapman',     'Drinks',   'Refreshing Nigerian classic mocktail with soft drinks and bitters.', 1500.00),
        ('Sweet Golden Puff Puff',     'Desserts', 'Portion of 6 sweet, pillowy soft fried dough balls.', 800.00),
    ]

    for name, cat_name, desc, price in foods:
        food, created = FoodItem.objects.get_or_create(
            name=name,
            defaults={
                'category': categories[cat_name],
                'description': desc,
                'base_price': price,
                'is_available': True,
            }
        )
        if created:
            print(f"  ✓ Created food: {name}")

    print("  Seeding complete.")

except Exception as e:
    print(f"  ! Seeding error: {e}")

print("\n" + "=" * 60)
print("BUILD SCRIPT COMPLETE")
print("=" * 60)
