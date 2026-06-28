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

# Step A: Run all non-kitchen framework migrations first (creates django_session, auth tables, etc.)
try:
    # Exclude kitchen since we'll handle it separately
    for app in ['contenttypes', 'auth', 'sessions', 'admin', 'messages']:
        try:
            call_command('migrate', app, verbosity=0)
        except Exception as ae:
            print(f"  ! {app} migrate: {ae}")
    print("  ✓ Framework migrations applied (sessions, auth, admin)")
except Exception as e:
    print(f"  ! Framework migrations failed: {e}")

# Step B: Fake kitchen 0001 (tables already created by raw SQL above)
try:
    call_command('migrate', '--fake', 'kitchen', '0001', verbosity=0)
    print("  ✓ Faked kitchen 0001_initial")
except Exception as e:
    print(f"  ! Fake 0001 (may already be applied): {e}")

# Step C: Apply kitchen 0002+ (ALTER TABLE repairs)
try:
    call_command('migrate', 'kitchen', verbosity=1)
    print("  ✓ Applied kitchen migrations (0002+)")
except Exception as e:
    print(f"  ! kitchen migrations failed: {e}")

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

    # -------------------------------------------------------
    # Option Groups & Choices (toppings / spice levels)
    # -------------------------------------------------------
    from kitchen.models import OptionGroup, OptionChoice, FoodItemOption

    option_groups_data = {
        'Spice Level': [
            ('Mild', 0.00),
            ('Medium', 0.00),
            ('Hot', 0.00),
            ('Extra Hot', 0.00),
        ],
        'Protein Add-On': [
            ('Extra Chicken', 500.00),
            ('Extra Beef', 500.00),
            ('Extra Fish', 600.00),
            ('Extra Prawns', 700.00),
        ],
        'Extra Sides': [
            ('Plantain', 300.00),
            ('Coleslaw', 200.00),
            ('Moi Moi', 400.00),
            ('Extra Sauce', 150.00),
        ],
    }

    groups = {}
    for group_name, choices in option_groups_data.items():
        grp, created = OptionGroup.objects.get_or_create(name=group_name)
        groups[group_name] = grp
        if created:
            print(f"  ✓ Created option group: {group_name}")
        for choice_name, delta in choices:
            OptionChoice.objects.get_or_create(
                group=grp,
                name=choice_name,
                defaults={'price_delta': delta}
            )

    # Attach option groups to food items
    # (Spice Level → all items; Protein Add-On + Extra Sides → rice/soups/grills)
    all_foods = FoodItem.objects.all()
    rice_soup_grill_names = {
        'Smoky Party Jollof Rice', 'Special Fried Rice',
        'Efo Riro Native Soup', 'Egusi Soup', 'Spiced Suya Platter'
    }

    for food in all_foods:
        # Spice Level for every food
        FoodItemOption.objects.get_or_create(food=food, group=groups['Spice Level'])
        # Protein + Sides for rice/soup/grill items
        if food.name in rice_soup_grill_names:
            FoodItemOption.objects.get_or_create(food=food, group=groups['Protein Add-On'])
            FoodItemOption.objects.get_or_create(food=food, group=groups['Extra Sides'])

    print("  ✓ Option groups and choices seeded.")
    print("  Seeding complete.")

except Exception as e:
    import traceback
    print(f"  ! Seeding error: {e}")
    print(traceback.format_exc())

print("\n" + "=" * 60)
print("BUILD SCRIPT COMPLETE")
print("=" * 60)
