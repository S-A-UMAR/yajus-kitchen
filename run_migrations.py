#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yajus_kitchen.settings')
django.setup()

from django.core.management import call_command
from django.db import connection, OperationalError, ProgrammingError

print("Starting migrations...")

# Try to check if 0001_initial is applied - make this very safe
initial_applied = False
try:
    with connection.cursor() as cursor:
        # Try to check django_migrations table (might not exist if fresh DB)
        try:
            cursor.execute("SELECT name FROM django_migrations WHERE app='kitchen' AND name='0001_initial'")
            if cursor.fetchone():
                initial_applied = True
        except (OperationalError, ProgrammingError):
            # Table doesn't exist or query failed - assume we need to run all migrations normally
            initial_applied = False
except Exception as e:
    print(f"Warning checking migration status: {e}")
    initial_applied = False

if not initial_applied:
    print("Attempting to fake kitchen 0001_initial migration...")
    try:
        call_command('migrate', '--fake', 'kitchen', '0001')
        print("Faked kitchen 0001_initial successfully!")
    except Exception as e:
        print(f"Note: Could not fake initial migration (maybe it's already applied or tables don't exist): {e}")

# Now run all migrations (this will apply 0002 and any others)
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
    
    # Temporarily disconnect post_save signals to avoid Profile issues
    try:
        from kitchen.models import create_user_profile, save_user_profile
        post_save.disconnect(create_user_profile, sender=User)
        post_save.disconnect(save_user_profile, sender=User)
    except Exception:
        pass
    
    # Create superuser
    try:
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@yajuskitchen.com', 'adminpassword123')
            print("Created superuser: admin")
        else:
            print("Superuser admin already exists")
    except Exception as e:
        print(f"Skipping superuser creation: {e}")
    
    # Create categories
    categories_data = ['Rice', 'Soups', 'Swallow', 'Grills', 'Drinks', 'Desserts']
    categories = {}
    for name in categories_data:
        cat, created = Category.objects.get_or_create(name=name)
        categories[name] = cat
        if created:
            print(f"Created category: {name}")
    
    # Create food items
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
