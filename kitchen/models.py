from decimal import Decimal
from pathlib import Path
from urllib.parse import quote
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        try:
            Profile.objects.get_or_create(user=instance)
        except Exception:
            pass


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            Profile.objects.get_or_create(user=instance)
    except Exception:
        pass


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class FoodItem(models.Model):
    name = models.CharField(max_length=150)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    description = models.TextField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='menu/', blank=True, null=True)
    is_available = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
            models.Index(fields=['is_available']),
        ]

    def __str__(self):
        return self.name

    @property
    def display_image_url(self):
        if self.image:
            return self.image.url

        # Predefined known static images (avoids filesystem checks)
        known_images = {
            'Smoky Party Jollof Rice': 'Smoky Party Jollof Rice.jpeg',
            'Special Fried Rice': 'Special Fried Rice.jpeg',
            'Efo Riro Native Soup': 'Efo Riro Native Soup.jpeg',
            'Egusi Soup': 'Egusi Soup.jpeg',
            'Premium Pounded Yam': 'Premium Pounded Yam.jpeg',
            'Oat Swallow': 'Oat Swallow.jpeg',
            'Spiced Suya Platter': 'Spiced Suya Platter.jpeg',
            'Yaju Signature Chapman': 'Yaju Signature Chapman.jpeg',
            'Sweet Golden Puff Puff': 'Sweet Golden Puff Puff.jpeg',
        }
        
        if self.name in known_images:
            return f"/static/img/menu/{quote(known_images[self.name])}"

        category_key = (self.category.name or '').strip().lower().replace(' ', '-')
        placeholders = {
            'rice': 'rice.svg',
            'soups': 'soup.svg',
            'soup': 'soup.svg',
            'swallow': 'swallow.svg',
            'grills': 'grill.svg',
            'grill': 'grill.svg',
            'drinks': 'drink.svg',
            'drink': 'drink.svg',
            'desserts': 'dessert.svg',
            'dessert': 'dessert.svg',
        }
        return f"/static/img/menu/{placeholders.get(category_key, 'meal.svg')}"


class OptionGroup(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name


class OptionChoice(models.Model):
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE, related_name='choices')
    name = models.CharField(max_length=100)
    price_delta = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"{self.group.name} - {self.name}"


class FoodItemOption(models.Model):
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='option_groups')
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('food', 'group')
    
    def __str__(self):
        return f"{self.food.name} - {self.group.name}"


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='cart')
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        identifier = self.user.username if self.user else f"Session {self.session_key[:8]}"
        return f"Cart for {identifier}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    selected_options = models.ManyToManyField(OptionChoice, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    
    def get_total_price(self):
        base = self.food.base_price
        for opt in self.selected_options.all():
            base += opt.price_delta
        return base * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('cooking', 'Cooking'),
        ('ready', 'Ready for Pickup'),
        ('out', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    guest_name = models.CharField(max_length=100, blank=True)
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=20, blank=True)
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    delivery_address = models.TextField(blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Order {self.order_number}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    food = models.ForeignKey(FoodItem, on_delete=models.SET_NULL, null=True)
    food_name = models.CharField(max_length=150)  # Denormalized for history
    food_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    selected_options = models.ManyToManyField(OptionChoice, blank=True)
    
    def get_item_total(self):
        base = self.food_price
        for opt in self.selected_options.all():
            base += opt.price_delta
        return base * self.quantity


class Payment(models.Model):
    PAYMENT_METHODS = [
        ('paystack', 'Paystack'),
        ('cash', 'Cash on Delivery'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Successful'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='paystack')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment {self.reference}"


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'food')
    
    def __str__(self):
        return f"{self.user.username} - {self.food.name}"
