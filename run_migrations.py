#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yajus_kitchen.settings')
django.setup()

from django.core.management import call_command
from django.db import connection, OperationalError, ProgrammingError

print("Starting migrations...")

# Manually create kitchen_profile table if it doesn't exist!
try:
    with connection.cursor() as cursor:
        try:
            cursor.execute("SHOW TABLES LIKE 'kitchen_profile'")
            if not cursor.fetchone():
                print("Creating kitchen_profile table...")
                cursor.execute("""
                    CREATE TABLE kitchen_profile (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        phone VARCHAR(15) DEFAULT '',
                        address TEXT DEFAULT '',
                        user_id BIGINT NOT NULL UNIQUE,
                        CONSTRAINT kitchen_profile_user_id_fk FOREIGN KEY (user_id) REFERENCES auth_user (id)
                    )
                """)
                print("Created kitchen_profile table!")
        except (OperationalError, ProgrammingError) as e:
            print(f"Warning creating profile table: {e}")
except Exception as e:
    print(f"Error checking profile table: {e}")

# Also check and create any other missing tables
try:
    with connection.cursor() as cursor:
        # Check kitchen_order table (our current order model)
        try:
            cursor.execute("SHOW TABLES LIKE 'kitchen_order'")
            if not cursor.fetchone():
                print("Creating kitchen_order table...")
                cursor.execute("""
                    CREATE TABLE kitchen_order (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        order_number VARCHAR(20) UNIQUE,
                        user_id BIGINT,
                        guest_name VARCHAR(100) DEFAULT '',
                        guest_email VARCHAR(254) DEFAULT '',
                        guest_phone VARCHAR(20) DEFAULT '',
                        total_amount DECIMAL(10,2),
                        status VARCHAR(20),
                        delivery_address TEXT,
                        special_instructions TEXT,
                        created_at DATETIME,
                        updated_at DATETIME,
                        CONSTRAINT kitchen_order_user_id_fk FOREIGN KEY (user_id) REFERENCES auth_user (id)
                    )
                """)
                print("Created kitchen_order table!")
        except (OperationalError, ProgrammingError):
            pass
        
        try:
            cursor.execute("SHOW TABLES LIKE 'kitchen_orderitem'")
            if not cursor.fetchone():
                print("Creating kitchen_orderitem table...")
                cursor.execute("""
                    CREATE TABLE kitchen_orderitem (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        order_id BIGINT NOT NULL,
                        food_id BIGINT,
                        food_name VARCHAR(150),
                        food_price DECIMAL(10,2),
                        quantity INT UNSIGNED NOT NULL,
                        CONSTRAINT kitchen_orderitem_order_id_fk FOREIGN KEY (order_id) REFERENCES kitchen_order (id),
                        CONSTRAINT kitchen_orderitem_food_id_fk FOREIGN KEY (food_id) REFERENCES kitchen_fooditem (id)
                    )
                """)
                print("Created kitchen_orderitem table!")
        except (OperationalError, ProgrammingError):
            pass
        
        try:
            cursor.execute("SHOW TABLES LIKE 'kitchen_payment'")
            if not cursor.fetchone():
                print("Creating kitchen_payment table...")
                cursor.execute("""
                    CREATE TABLE kitchen_payment (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        order_id BIGINT NOT NULL UNIQUE,
                        reference VARCHAR(100) UNIQUE,
                        amount DECIMAL(10,2),
                        method VARCHAR(20),
                        status VARCHAR(20),
                        created_at DATETIME,
                        CONSTRAINT kitchen_payment_order_id_fk FOREIGN KEY (order_id) REFERENCES kitchen_order (id)
                    )
                """)
                print("Created kitchen_payment table!")
        except (OperationalError, ProgrammingError):
            pass
        
        try:
            cursor.execute("SHOW TABLES LIKE 'kitchen_fooditemoption'")
            if not cursor.fetchone():
                print("Creating kitchen_fooditemoption table...")
                cursor.execute("""
                    CREATE TABLE kitchen_fooditemoption (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        food_id BIGINT NOT NULL,
                        group_id BIGINT NOT NULL,
                        UNIQUE KEY (food_id, group_id),
                        CONSTRAINT kitchen_fooditemoption_food_id_fk FOREIGN KEY (food_id) REFERENCES kitchen_fooditem (id),
                        CONSTRAINT kitchen_fooditemoption_group_id_fk FOREIGN KEY (group_id) REFERENCES kitchen_optiongroup (id)
                    )
                """)
                print("Created kitchen_fooditemoption table!")
        except (OperationalError, ProgrammingError):
            pass
            
except Exception as e:
    print(f"Error creating tables: {e}")

# Now try to fake 0001
try:
    call_command('migrate', '--fake', 'kitchen', '0001')
    print("Faked 0001 successfully!")
except Exception as e:
    print(f"Error faking 0001: {e}")

print("Running all migrations...")
try:
    call_command('migrate')
    print("Migrations completed successfully!")
except Exception as e:
    print(f"Error running migrations: {e}")

# Now seed the database
print("Starting database seeding...")
try:
    from django.contrib.auth.models import User
    from kitchen.models import Category, FoodItem, OptionGroup, OptionChoice, FoodItemOption
    from django.db.models.signals import post_save
    
    try:
        from kitchen.models import create_user_profile, save_user_profile
        post_save.disconnect(create_user_profile, sender=User)
        post_save.disconnect(save_user_profile, sender=User)
    except Exception:
        pass
    
    try:
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@yajuskitchen.com', 'adminpassword123')
            print("Created superuser: admin")
        else:
            print("Superuser admin already exists")
    except Exception as e:
        print(f"Skipping superuser creation: {e}")
    
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
        {'name': 'Sweet Golden Puff Puff', 'category': 'Desserts', 'description': 'Portion of 6 sweet, pillowy soft fried dough balls.', 'base_price': 800.00}
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
    print(f"Seeding error (but migrations still ran): {e}")
