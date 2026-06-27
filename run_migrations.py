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

# Try to apply migrations normally first!
try:
    print("Running migrations normally...")
    call_command('migrate')
    print("Migrations applied normally!")
except (OperationalError, ProgrammingError) as e:
    print(f"Normal migration failed: {e}")
    print("Trying to fake initial migration...")
    try:
        call_command('migrate', '--fake', 'kitchen', '0001')
        print("Faked initial migration! Now running all migrations again...")
        call_command('migrate')
        print("All migrations completed after faking initial!")
    except Exception as e2:
        print(f"Failed to fake initial: {e2}")
except Exception as e:
    print(f"Unexpected error: {e}")

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
