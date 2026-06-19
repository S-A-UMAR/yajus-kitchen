import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yajus_kitchen.settings')
django.setup()

from django.contrib.auth.models import User
from kitchen.models import Category, FoodItem, OptionGroup, OptionChoice, FoodItemOption

def seed():
    print("Seeding database with mock data...")
    
    # 1. Create Default Superuser
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@yajuskitchen.com', 'adminpassword123')
        print("Created superuser: admin / adminpassword123")
    else:
        print("Superuser admin already exists.")

    # 2. Create Categories
    categories_data = ['Rice', 'Soups', 'Swallow', 'Grills', 'Drinks', 'Desserts']
    categories = {}
    for name in categories_data:
        cat, created = Category.objects.get_or_create(name=name)
        categories[name] = cat
        if created:
            print(f"Created category: {name}")

    # 3. Create Option Groups
    spice_group, _ = OptionGroup.objects.get_or_create(name="Spice Level")
    toppings_group, _ = OptionGroup.objects.get_or_create(name="Extra Toppings")
    
    # Create Option Choices
    spice_choices = [
        ("Mild", 0.00),
        ("Medium", 0.00),
        ("Hot", 0.00)
    ]
    for name, delta in spice_choices:
        OptionChoice.objects.get_or_create(group=spice_group, name=name, defaults={'price_delta': delta})
        
    toppings_choices = [
        ("Grilled Chicken", 2000.00),
        ("Assorted Meat", 1500.00),
        ("Fried Fish", 2500.00),
        ("Boiled Egg", 500.00)
    ]
    for name, delta in toppings_choices:
        OptionChoice.objects.get_or_create(group=toppings_group, name=name, defaults={'price_delta': delta})

    print("Created option choices and groups.")

    # 4. Create Food Items
    foods = [
        {
            'name': 'Smoky Party Jollof Rice',
            'category': categories['Rice'],
            'description': 'Premium smokey Jollof served with sweet fried plantain and salad.',
            'base_price': 3500.00,
            'has_spice': True,
            'has_toppings': True
        },
        {
            'name': 'Special Fried Rice',
            'category': categories['Rice'],
            'description': 'Deliciously stir-fried rice loaded with fresh vegetables and eggs.',
            'base_price': 3800.00,
            'has_spice': False,
            'has_toppings': True
        },
        {
            'name': 'Efo Riro Native Soup',
            'category': categories['Soups'],
            'description': 'Rich Yoruba spinach soup stewed in palm oil, iru, and stock fish.',
            'base_price': 4500.00,
            'has_spice': True,
            'has_toppings': True
        },
        {
            'name': 'Egusi Soup',
            'category': categories['Soups'],
            'description': 'Traditional Nigerian melon seed soup enriched with pumpkin leaves.',
            'base_price': 4200.00,
            'has_spice': True,
            'has_toppings': True
        },
        {
            'name': 'Premium Pounded Yam',
            'category': categories['Swallow'],
            'description': 'Smooth, fluffy, and stretchy pounded yam. Best paired with Efo Riro.',
            'base_price': 1000.00,
            'has_spice': False,
            'has_toppings': False
        },
        {
            'name': 'Oat Swallow',
            'category': categories['Swallow'],
            'description': 'Healthy whole-grain swallow option high in fiber.',
            'base_price': 1200.00,
            'has_spice': False,
            'has_toppings': False
        },
        {
            'name': 'Spiced Suya Platter',
            'category': categories['Grills'],
            'description': 'Thinly sliced grilled beef skewers coated with spicy yaji pepper.',
            'base_price': 5000.00,
            'has_spice': True,
            'has_toppings': False
        },
        {
            'name': 'Yaju Signature Chapman',
            'category': categories['Drinks'],
            'description': 'Refreshing Nigerian classic mocktail with soft drinks and angostura bitters.',
            'base_price': 1500.00,
            'has_spice': False,
            'has_toppings': False
        },
        {
            'name': 'Sweet Golden Puff Puff',
            'category': categories['Desserts'],
            'description': 'Portion of 6 sweet, pillowy soft fried dough balls.',
            'base_price': 800.00,
            'has_spice': False,
            'has_toppings': False
        }
    ]

    for f_data in foods:
        food, created = FoodItem.objects.get_or_create(
            name=f_data['name'],
            defaults={
                'category': f_data['category'],
                'description': f_data['description'],
                'base_price': f_data['base_price'],
                'is_available': True
            }
        )
        if created:
            print(f"Created food item: {food.name}")
            
        # Link options
        if f_data['has_spice']:
            FoodItemOption.objects.get_or_create(food=food, group=spice_group)
        if f_data['has_toppings']:
            FoodItemOption.objects.get_or_create(food=food, group=toppings_group)

    print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed()
