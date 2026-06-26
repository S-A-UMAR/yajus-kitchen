import os
import json
import hmac
import hashlib
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils import timezone
from django.conf import settings

from .models import (
    Category, FoodItem, OptionChoice, OptionGroup,
    Cart, CartItem, Order, OrderItem, Payment, Review
)
from .context_processors import get_or_create_cart


# 1. Customer Pages

def home_view(request):
    """
    Renders the Home Page. Shows popular items, categories, and testimonials.
    """
    categories = Category.objects.all()[:4]
    popular_items = FoodItem.objects.filter(is_available=True).select_related('category')[:3]
    return render(request, 'kitchen/home.html', {
        'categories': categories,
        'popular_items': popular_items
    })


def menu_view(request):
    """
    Renders the Menu Page with Categories, Search, Filters, and Cart drawer trigger.
    """
    categories = Category.objects.all()
    selected_category_id = request.GET.get('category')
    search_query = request.GET.get('search')
    
    food_items = FoodItem.objects.filter(is_available=True).select_related('category')
    
    if selected_category_id:
        food_items = food_items.filter(category_id=selected_category_id)
        
    if search_query:
        food_items = food_items.filter(name__icontains=search_query)
        
    return render(request, 'kitchen/menu.html', {
        'categories': categories,
        'food_items': food_items,
        'selected_category_id': int(selected_category_id) if selected_category_id else None,
        'search_query': search_query or ''
    })


def food_detail_view(request, food_id):
    """
    API view: Returns custom options for a FoodItem in JSON for the Customizer modal.
    """
    food = get_object_or_404(FoodItem, id=food_id)
    # Get associated option groups
    groups = OptionGroup.objects.filter(fooditemoption__food=food).prefetch_related('choices')
    
    groups_data = []
    for g in groups:
        choices_data = []
        for c in g.choices.all():
            choices_data.append({
                'id': c.id,
                'name': c.name,
                'price_delta': float(c.price_delta)
            })
        groups_data.append({
            'id': g.id,
            'name': g.name,
            'choices': choices_data
        })
        
    return JsonResponse({
        'id': food.id,
        'name': food.name,
        'base_price': float(food.base_price),
        'description': food.description,
        'image': food.display_image_url,
        'groups': groups_data
    })


# 2. Cart Operations (Ajax & Normal Views)

def cart_view(request):
    """
    Renders the dedicated Cart review page.
    """
    return render(request, 'kitchen/cart.html')


def cart_add_view(request, food_id):
    """
    Add food item with customization options to the active cart.
    Accepts POST data with option choice IDs.
    """
    if request.method == 'POST':
        food = get_object_or_404(FoodItem, id=food_id)
        cart = get_or_create_cart(request)
        
        # Get selected option IDs
        option_ids = request.POST.getlist('options')
        qty = int(request.POST.get('quantity', 1))
        
        # Parse selected options
        choices = OptionChoice.objects.filter(id__in=option_ids)
        
        # Find if same item with EXACTLY the same options already exists in cart
        cart_items = cart.items.filter(food=food)
        target_item = None
        
        for item in cart_items:
            # Get list of option IDs for this item
            item_opt_ids = set(item.selected_options.values_list('id', flat=True))
            query_opt_ids = set(int(x) for x in option_ids)
            if item_opt_ids == query_opt_ids:
                target_item = item
                break
                
        if target_item:
            target_item.quantity += qty
            target_item.save()
        else:
            target_item = CartItem.objects.create(cart=cart, food=food, quantity=qty)
            if choices.exists():
                target_item.selected_options.set(choices)
                
        return JsonResponse({
            'success': True,
            'message': f"Added {food.name} to cart!",
            'total_qty': sum(item.quantity for item in cart.items.all())
        })
        
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)


def cart_update_view(request, item_id):
    """
    Updates the quantity of a cart item.
    """
    if request.method == 'POST':
        cart = get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        
        qty = int(request.POST.get('quantity', 1))
        if qty <= 0:
            item.delete()
        else:
            item.quantity = qty
            item.save()
            
        return JsonResponse({
            'success': True,
            'item_total': float(item.total_price) if qty > 0 else 0,
            'cart_total': float(cart.total_price),
            'cart_qty': sum(i.quantity for i in cart.items.all())
        })
        
    return JsonResponse({'success': False}, status=400)


def cart_remove_view(request, item_id):
    """
    Removes an item from the cart.
    """
    if request.method == 'POST':
        cart = get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        
        return JsonResponse({
            'success': True,
            'cart_total': float(cart.total_price),
            'cart_qty': sum(i.quantity for i in cart.items.all())
        })
        
    return JsonResponse({'success': False}, status=400)


def cart_drawer_partial(request):
    """
    Returns the HTML content of the cart drawer.
    Used for live updates without full page reloads.
    """
    return render(request, 'kitchen/partials/cart_drawer.html')


# 3. Checkout & Payment

def checkout_view(request):
    """
    Renders the Checkout page. Handles guest checkout vs authenticated checkout.
    """
    cart = get_or_create_cart(request)
    if not cart.items.exists():
        messages.warning(request, "Your cart is empty!")
        return redirect('menu')
        
    if request.method == 'POST':
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        # Check if the user chose to create an account
        create_account = request.POST.get('create_account') == 'on'
        password = request.POST.get('password')
        
        user = None
        if request.user.is_authenticated:
            user = request.user
            # Update user profile with phone and address
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone = phone
            profile.address = address
            profile.save()
        elif create_account and email and password:
            # Register user
            if User.objects.filter(username=email).exists():
                messages.error(request, "An account with this email already exists.")
                return redirect('checkout')
            
            user = User.objects.create_user(username=email, email=email, password=password)
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone = phone
            profile.address = address
            profile.save()
            login(request, user)
            
        # Create Order
        order = Order.objects.create(
            user=user,
            email=email or (user.email if user else ''),
            phone=phone,
            delivery_address=address,
            total=cart.total_price,
            is_guest=not (user or request.user.is_authenticated)
        )
        
        # Create OrderItems
        for cart_item in cart.items.all():
            options_text_list = []
            for opt in cart_item.selected_options.all():
                if opt.price_delta > 0:
                    options_text_list.append(f"{opt.name} (+₦{opt.price_delta})")
                else:
                    options_text_list.append(opt.name)
            options_summary = ", ".join(options_text_list)
            
            OrderItem.objects.create(
                order=order,
                food=cart_item.food,
                food_name=cart_item.food.name,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                options_summary=options_summary
            )
            
        # Redirect to payment setup page
        return redirect('payment_initialize', order_id=order.id)
        
    # For GET requests, prefill profile if authenticated
    prefill = {}
    if request.user.is_authenticated:
        prefill['email'] = request.user.email
        profile, _ = Profile.objects.get_or_create(user=request.user)
        prefill['phone'] = profile.phone
        prefill['address'] = profile.address
        
    return render(request, 'kitchen/checkout.html', {
        'prefill': prefill
    })


def payment_initialize_view(request, order_id):
    """
    Initializes a transaction on Paystack, or redirects to mock payment page if credentials are missing.
    """
    order = get_object_or_404(Order, id=order_id)
    
    paystack_secret = settings.PAYSTACK_SECRET_KEY
    if not paystack_secret:
        # Fallback to local mock checkout screen
        return redirect('mock_checkout', order_id=order.id)
        
    # Calculate amount in Kobo
    amount_kobo = int(order.total * 100)
    reference = f"YJ_{order.id}_{int(timezone.now().timestamp())}"
    
    # Create or update Payment
    Payment.objects.update_or_create(
        order=order,
        defaults={
            'amount': order.total,
            'reference': reference,
            'status': 'pending',
            'provider': 'Paystack'
        }
    )
    
    callback_url = request.build_absolute_uri('/payment/callback/')
    
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {paystack_secret}",
        "Content-Type": "application/json"
    }
    payload = {
        "email": order.email,
        "amount": amount_kobo,
        "callback_url": callback_url,
        "reference": reference
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        res_data = response.json()
        if res_data.get('status'):
            auth_url = res_data['data']['authorization_url']
            return redirect(auth_url)
        else:
            messages.error(request, f"Paystack Initialization failed: {res_data.get('message')}")
            return redirect('mock_checkout', order_id=order.id)
    except Exception as e:
        messages.warning(request, f"Could not connect to Paystack: {e}. Loading local mock payment dashboard.")
        return redirect('mock_checkout', order_id=order.id)


def payment_callback_view(request):
    """
    Verifies payment with Paystack callback reference.
    """
    reference = request.GET.get('reference')
    if not reference:
        messages.error(request, "Payment reference missing.")
        return redirect('menu')
        
    payment = get_object_or_404(Payment, reference=reference)
    order = payment.order
    
    paystack_secret = settings.PAYSTACK_SECRET_KEY
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {paystack_secret}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        res_data = response.json()
        if res_data.get('status') and res_data['data']['status'] == 'success':
            # Complete payment
            payment.status = 'success'
            payment.save()
            
            order.status = 'received'
            order.save()
            
            # Clear Cart
            cart = get_or_create_cart(request)
            cart.items.all().delete()
            
            messages.success(request, "Payment verified successfully!")
            return redirect('order_success', order_id=order.id)
        else:
            payment.status = 'failed'
            payment.save()
            messages.error(request, "Payment verification failed.")
            return redirect('checkout')
    except Exception as e:
        messages.error(request, f"Verification error: {e}")
        return redirect('checkout')


@csrf_exempt
def payment_webhook_view(request):
    """
    Secures webhook for transaction completions. HMAC verification ensures authenticity.
    """
    paystack_signature = request.headers.get('x-paystack-signature')
    if not paystack_signature:
        return HttpResponseForbidden("Signature missing")
        
    paystack_secret = settings.PAYSTACK_WEBHOOK_SECRET or settings.PAYSTACK_SECRET_KEY
    if not paystack_secret:
        return HttpResponse("Local fallback active", status=200)
        
    # Verify signature
    body = request.body
    computed_signature = hmac.new(
        paystack_secret.encode('utf-8'),
        body,
        hashlib.sha512
    ).hexdigest()
    
    if not hmac.compare_digest(computed_signature, paystack_signature):
        return HttpResponseForbidden("Invalid signature")
        
    try:
        data = json.loads(body)
        if data.get('event') == 'charge.success':
            reference = data['data']['reference']
            payment = Payment.objects.filter(reference=reference).first()
            if payment:
                payment.status = 'success'
                payment.save()
                
                order = payment.order
                order.status = 'received'
                order.save()
                
                # Note: Webhook runs in background, so cart is cleared in callback
    except Exception as e:
        return HttpResponse(f"Error parsing request: {e}", status=400)
        
    return HttpResponse("OK", status=200)


def mock_checkout_view(request, order_id):
    """
    A simulated payment interface when keys are absent.
    """
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Create mock reference
        reference = f"MOCK_{order.id}_{int(timezone.now().timestamp())}"
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                'amount': order.total,
                'reference': reference,
                'provider': 'Mock Payment'
            }
        )
        
        if action == 'success':
            payment.status = 'success'
            payment.save()
            
            order.status = 'received'
            order.save()
            
            # Clear Cart
            cart = get_or_create_cart(request)
            cart.items.all().delete()
            
            messages.success(request, "Mock payment approved! Order is now received.")
            return redirect('order_success', order_id=order.id)
        else:
            payment.status = 'failed'
            payment.save()
            order.status = 'cancelled'
            order.save()
            messages.error(request, "Mock payment declined.")
            return redirect('checkout')
            
    return render(request, 'kitchen/mock_checkout.html', {'order': order})


def order_success_view(request, order_id):
    """
    Displays the receipt and confirmation.
    """
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'kitchen/order_success.html', {'order': order})


def order_detail_view(request, order_id):
    """
    Visualizes tracking status timeline.
    """
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'kitchen/order_detail.html', {'order': order})


def order_status_api(request, order_id):
    """
    JSON status endpoint for UI polling updates.
    """
    order = get_object_or_404(Order, id=order_id)
    return JsonResponse({
        'status': order.status,
        'status_display': order.get_status_display(),
        'updated_at': order.updated_at.strftime('%Y-%m-%d %H:%M:%S')
    })


# 4. User Dashboard & Core Views

@login_required
def dashboard_view(request):
    """
    Customer dashboard displaying orders and profiles.
    """
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    # Ensure user has a profile
    Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Reorder previous order
        order_id = request.POST.get('reorder_id')
        if order_id:
            old_order = get_object_or_404(Order, id=order_id, user=request.user)
            cart = get_or_create_cart(request)
            
            # Transfer items to cart
            for item in old_order.items.all():
                if item.food and item.food.is_available:
                    # Create CartItem
                    cart_item = CartItem.objects.create(
                        cart=cart,
                        food=item.food,
                        quantity=item.quantity
                    )
                    # Note: options snapshot is text, we can't fully rebuild choice models perfectly
                    # but we look them up if their names match
                    if item.options_summary:
                        option_names = [opt.split(' (+')[0].strip() for opt in item.options_summary.split(',')]
                        choices = OptionChoice.objects.filter(name__in=option_names)
                        if choices.exists():
                            cart_item.selected_options.set(choices)
            messages.success(request, f"Items from Order #{old_order.id} added to your cart!")
            return redirect('cart')
            
    return render(request, 'kitchen/dashboard.html', {
        'orders': orders
    })


def contact_view(request):
    """
    Contact details page.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        # In a real app, send mail. For now, display alert.
        messages.success(request, f"Thank you {name}, we have received your inquiry!")
        return redirect('contact')
    return render(request, 'kitchen/contact.html')


# 5. Auth Views

def login_view(request):
    """
    Visual User Login page.
    """
    if request.user.is_authenticated:
        return redirect('menu')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('menu')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
        
    return render(request, 'kitchen/login.html', {'form': form})


def register_view(request):
    """
    Visual User Sign-Up page.
    """
    if request.user.is_authenticated:
        return redirect('menu')
        
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Login immediately
            login(request, user)
            messages.success(request, "Account created successfully! Welcome to Yaju's Kitchen.")
            return redirect('menu')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = UserCreationForm()
        
    return render(request, 'kitchen/register.html', {'form': form})


def add_review_view(request, food_id):
    """
    Post review feedback on individual items.
    """
    if request.method == 'POST' and request.user.is_authenticated:
        food = get_object_or_404(FoodItem, id=food_id)
        rating = int(request.POST.get('rating', 5))
        comment = request.POST.get('comment', '')
        
        Review.objects.create(
            user=request.user,
            food=food,
            rating=rating,
            comment=comment
        )
        messages.success(request, "Thank you for reviewing this meal!")
        return redirect('menu')
    return redirect('menu')
