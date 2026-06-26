import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yajus_kitchen.settings')
django.setup()

from django.contrib.auth.models import User
from kitchen.models import Category, FoodItem, OptionGroup, OptionChoice, FoodItemOption
from kitchen.models import create_user_profile, save_user_profile

def seed():
    print("Seeding database with mock data...")
    
    # Temporarily disconnect post_save signals to avoid Profile creation issues
    from django.db.models.signals import post_save
    try:
        from kitchen.models import create_user_profile, save_user_profile
        post_save.disconnect(create_user_profile, sender=User)
        post_save.disconnect(save_user_profile, sender=User)
    except Exception:
        pass
    
    # 1. Create Default Superuser (skip if signals cause issues)
    try:
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@yajuskitchen.com', 'adminpassword123')
            print("Created superuser: admin / adminpassword123")
        else:
            print("Superuser admin already exists.")
    except Exception as e:
        print(f"Skipping superuser creation: {e}")

    # 2. Create Categories
    categories_data = ['Rice', 'Soups', 'Swallow', 'Grills', 'Drinks', 'Desserts']
    categories = {}
    for name in categories_data:
        cat, created = Category.objects.get_or_create(name=name)
        categories[name] = cat
        if created:
            print(f"Created category: {name}")

    # 3. Create Food Items - ensure they're available! Skip options for now
    foods = [
        {
            'name': 'Smoky Party Jollof Rice',
            'category': categories['Rice'],
            'description': 'Premium smokey Jollof served with sweet fried plantain and salad.',
            'base_price': 3500.00
        },
        {
            'name': 'Special Fried Rice',
            'category': categories['Rice'],
            'description': 'Deliciously stir-fried rice loaded with fresh vegetables and eggs.',
            'base_price': 3800.00
        },
        {
            'name': 'Efo Riro Native Soup',
            'category': categories['Soups'],
            'description': 'Rich Yoruba spinach soup stewed in palm oil, iru, and stock fish.',
            'base_price': 4500.00
        },
        {
            'name': 'Egusi Soup',
            'category': categories['Soups'],
            'description': 'Traditional Nigerian melon seed soup enriched with pumpkin leaves.',
            'base_price': 4200.00
        },
        {
            'name': 'Premium Pounded Yam',
            'category': categories['Swallow'],
            'description': 'Smooth, fluffy, and stretchy pounded yam. Best paired with Efo Riro.',
            'base_price': 1000.00
        },
        {
            'name': 'Oat Swallow',
            'category': categories['Swallow'],
            'description': 'Healthy whole-grain swallow option high in fiber.',
            'base_price': 1200.00
        },
        {
            'name': 'Spiced Suya Platter',
            'category': categories['Grills'],
            'description': 'Thinly sliced grilled beef skewers coated with spicy yaji pepper.',
            'base_price': 5000.00
        },
        {
            'name': 'Yaju Signature Chapman',
            'category': categories['Drinks'],
            'description': 'Refreshing Nigerian classic mocktail with soft drinks and angostura bitters.',
            'base_price': 1500.00
        },
        {
            'name': 'Sweet Golden Puff Puff',
            'category': categories['Desserts'],
            'description': 'Portion of 6 sweet, pillowy soft fried dough balls.',
            'base_price': 800.00
        }
    ]

    for f_data in foods:
        # Get or create food, and ensure is_available is True!
        food, created = FoodItem.objects.get_or_create(
            name=f_data['name'],
            defaults={
                'category': f_data['category'],
                'description': f_data['description'],
                'base_price': f_data['base_price'],
                'is_available': True
            }
        )
        # Make sure it's available even if it existed before!
        if not food.is_available:
            food.is_available = True
            food.save()
            
        if created:
            print(f"Created food item: {food.name}")

    print(f"Total food items now in database: {FoodItem.objects.count()}")
    print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed()
