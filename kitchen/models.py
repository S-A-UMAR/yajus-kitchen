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
    
    # Stock/Inventory Management
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Current available stock")
    low_stock_threshold = models.PositiveIntegerField(default=10, help_text="Alert when stock falls below this")
    track_stock = models.BooleanField(default=True, help_text="Enable automatic stock tracking")
    
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

    @property
    def is_low_stock(self):
        """Check if item is running low on stock"""
        if not self.track_stock:
            return False
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def stock_status(self):
        """Get human-readable stock status"""
        if not self.track_stock:
            return "Not Tracked"
        if self.stock_quantity == 0:
            return "Out of Stock"
        if self.is_low_stock:
            return f"Low Stock ({self.stock_quantity})"
        return f"In Stock ({self.stock_quantity})"

    def decrease_stock(self, quantity=1):
        """Decrease stock quantity and update availability"""
        if not self.track_stock:
            return True
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            if self.stock_quantity == 0:
                self.is_available = False
            self.save(update_fields=['stock_quantity', 'is_available'])
            return True
        return False

    def increase_stock(self, quantity=1):
        """Increase stock quantity"""
        if not self.track_stock:
            return
        self.stock_quantity += quantity
        if self.stock_quantity > 0 and not self.is_available:
            self.is_available = True
        self.save(update_fields=['stock_quantity', 'is_available'])



class OptionGroup(models.Model):
    name = models.CharField(max_length=100) # e.g. "Toppings", "Spice Level"
    
    def __str__(self):
        return self.name


class OptionChoice(models.Model):
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE, related_name='choices')
    name = models.CharField(max_length=100) # e.g. "Extra Beef", "Mild", "Hot"
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        if self.price_delta > 0:
            return f"{self.name} (+₦{self.price_delta})"
        return self.name


class FoodItemOption(models.Model):
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='options')
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('food', 'group')

    def __str__(self):
        return f"{self.food.name} - {self.group.name}"


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.user:
            return f"Cart of {self.user.username}"
        return f"Guest Cart ({self.session_key})"

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    selected_options = models.ManyToManyField(OptionChoice, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.food.name} in Cart"

    @property
    def unit_price(self):
        # Base price + sum of price deltas of selected options
        # Explicitly cast to Decimal to handle SQLite returning floats in tests
        option_deltas = sum(
            (Decimal(str(option.price_delta)) for option in self.selected_options.all()),
            Decimal('0.00')
        )
        return Decimal(str(self.food.base_price)) + option_deltas

    @property
    def total_price(self):
        return self.unit_price * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('preparing', 'Preparing'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ]
    
    # Define valid status transitions (from -> [to, ...])
    STATUS_TRANSITIONS = {
        'received': ['preparing', 'cancelled'],
        'preparing': ['out_for_delivery', 'cancelled'],
        'out_for_delivery': ['delivered'],
        'delivered': [],  # Final state
        'cancelled': [],  # Final state
    }
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    delivery_address = models.TextField()
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='received')
    total = models.DecimalField(max_digits=12, decimal_places=2)
    is_guest = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} ({self.status})"
    
    def can_transition_to(self, new_status):
        """Check if current status can transition to new_status"""
        return new_status in self.STATUS_TRANSITIONS.get(self.status, [])
    
    def clean(self):
        """Validate status transitions on model clean"""
        from django.core.exceptions import ValidationError
        
        # Skip validation for new objects
        if self.pk is None:
            return
            
        # Get current status from database
        try:
            old_order = Order.objects.get(pk=self.pk)
            if old_order.status != self.status:
                if not old_order.can_transition_to(self.status):
                    raise ValidationError({
                        'status': f'Cannot transition from "{old_order.get_status_display()}" to "{self.get_status_display()}". '
                                  f'Allowed transitions: {", ".join([dict(self.STATUS_CHOICES)[s] for s in self.STATUS_TRANSITIONS.get(old_order.status, [])])}'
                    })
        except Order.DoesNotExist:
            pass
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['email']),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    food = models.ForeignKey(FoodItem, on_delete=models.SET_NULL, null=True)
    food_name = models.CharField(max_length=150) # Backup in case food is deleted
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) # Snapshotted price
    options_summary = models.TextField(blank=True) # Snapshotted list of options, e.g. "Extra Beef (+₦500.00), Mild"

    def __str__(self):
        return f"{self.quantity} x {self.food_name} in Order #{self.order.id}"

    @property
    def total_price(self):
        return self.unit_price * self.quantity


class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    provider = models.CharField(max_length=50, default='Paystack')
    status = models.CharField(max_length=25, default='pending') # pending, success, failed
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for Order #{self.order.id} ({self.status})"


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField() # 1 to 5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.user.username} on {self.food.name} ({self.rating} stars)"


@receiver(post_save, sender=Order)
def order_status_changed(sender, instance, created, **kwargs):
    """Send email notification when order status changes."""
    if created:
        return

    try:
        old_order = Order.objects.get(pk=instance.pk)
        if old_order.status != instance.status:
            from .email_utils import send_order_status_update_email

            send_order_status_update_email(instance, old_order.status)
    except Order.DoesNotExist:
        pass
