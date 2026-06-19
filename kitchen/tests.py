import json
import hmac
import hashlib
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

from .models import Category, FoodItem, OptionGroup, OptionChoice, Cart, CartItem, Order, Payment


class CartCalculationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Test Category")
        self.food = FoodItem.objects.create(
            name="Test Dish",
            category=self.category,
            description="Test desc",
            base_price=1000.00
        )
        self.option_group = OptionGroup.objects.create(name="Test Options")
        self.choice1 = OptionChoice.objects.create(
            group=self.option_group, name="Extra Beef", price_delta=500.00
        )
        self.choice2 = OptionChoice.objects.create(
            group=self.option_group, name="Extra Cheese", price_delta=200.00
        )
        self.user = User.objects.create_user(
            username="testuser", email="test@mail.com", password="testpassword"
        )

    def test_cart_item_unit_price_with_options(self):
        """CartItem unit price should be base + sum of option price deltas."""
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, food=self.food, quantity=1)
        cart_item.selected_options.add(self.choice1, self.choice2)
        # unit_price = 1000 + 500 + 200 = 1700
        self.assertEqual(float(cart_item.unit_price), 1700.00)

    def test_cart_item_total_price_with_quantity(self):
        """CartItem total price should multiply unit price by quantity."""
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, food=self.food, quantity=2)
        cart_item.selected_options.add(self.choice1, self.choice2)
        # total_price = 1700 * 2 = 3400
        self.assertEqual(float(cart_item.total_price), 3400.00)

    def test_cart_total_price(self):
        """Cart total should reflect sum of all cart item totals."""
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, food=self.food, quantity=2)
        item.selected_options.add(self.choice1)
        # unit = 1000 + 500 = 1500, total = 1500 * 2 = 3000
        self.assertEqual(float(cart.total_price), 3000.00)

    def test_cart_empty_total(self):
        """Empty cart should return 0 as total price."""
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(float(cart.total_price), 0)


class FoodDetailAPITests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Grills")
        self.food = FoodItem.objects.create(
            name="Suya Platter",
            category=self.category,
            description="Spicy grilled beef skewers",
            base_price=5000.00
        )
        self.client = Client()

    def test_food_detail_returns_json(self):
        """Food detail view should return JSON with id, name, and base_price."""
        url = reverse('food_detail', args=[self.food.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.food.id)
        self.assertEqual(data['name'], self.food.name)
        self.assertEqual(float(data['base_price']), 5000.00)
        self.assertIn('groups', data)

    def test_food_detail_404_for_invalid_id(self):
        """Food detail view should return 404 for non-existent food IDs."""
        url = reverse('food_detail', args=[99999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class PaystackWebhookSecurityTests(TestCase):
    """
    Verifies the webhook HMAC-SHA512 security logic.
    """
    def setUp(self):
        self.client = Client()
        self.url = reverse('payment_webhook')
        self.payload = json.dumps({
            "event": "charge.success",
            "data": {"reference": "test_ref_001"}
        })

    def test_webhook_rejected_without_signature(self):
        """Webhook with no signature should return 403 Forbidden."""
        response = self.client.post(
            self.url, data=self.payload, content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)

    def test_webhook_rejected_with_wrong_signature(self):
        """Webhook with incorrect HMAC signature should return 403 Forbidden."""
        settings.PAYSTACK_WEBHOOK_SECRET = "correct_secret"
        response = self.client.post(
            self.url,
            data=self.payload,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE='completely_wrong_signature'
        )
        self.assertEqual(response.status_code, 403)

    def test_webhook_accepted_with_correct_signature(self):
        """Webhook with correct HMAC-SHA512 signature should return 200 OK."""
        secret = "correct_secret"
        settings.PAYSTACK_WEBHOOK_SECRET = secret
        settings.PAYSTACK_SECRET_KEY = secret

        correct_sig = hmac.new(
            secret.encode('utf-8'),
            self.payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        response = self.client.post(
            self.url,
            data=self.payload,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=correct_sig
        )
        self.assertEqual(response.status_code, 200)
