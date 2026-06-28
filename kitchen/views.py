import os
import json
import hmac
import hashlib
import csv
import traceback
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, Http404
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection
from django.db.models import Sum, Count
from django.utils import timezone
from django.conf import settings

from .email_utils import (
    send_order_confirmation_email,
    send_order_status_update_email,
    send_payment_confirmation_email
)

from .models import (
    Category, FoodItem, OptionChoice, OptionGroup,
    Cart, CartItem, Order, OrderItem, Payment, Review
)
from .context_processors import get_or_create_cart


# ── Debug / Diagnostic View ─────────────────────────────────────────────────

def debug_view(request):
    """
    Diagnostic endpoint — shows real DB/session errors.
    Visit /debug/ to see what is broken.
    """
    results = {}

    # 1. Check DB connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        results['db_connection'] = 'OK'
    except Exception as e:
        results['db_connection'] = f'ERROR: {e}'

    # 2. Check critical tables
    tables_to_check = [
        'django_session',
        'kitchen_cart',
        'kitchen_cartitem',
        'kitchen_cartitem_selected_options',
        'kitchen_orderitem_selected_options',
        'kitchen_optiongroup',
        'kitchen_optionchoice',
        'kitchen_fooditemoption',
    ]
    table_status = {}
    for table in tables_to_check:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                count = cursor.fetchone()[0]
                table_status[table] = f'EXISTS ({count} rows)'
        except Exception as e:
            table_status[table] = f'MISSING or ERROR: {e}'
    results['tables'] = table_status

    # 3. Check critical columns
    columns_to_check = [
        ('kitchen_optionchoice', 'group_id'),
        ('kitchen_optionchoice', 'price_delta'),
        ('kitchen_cart', 'session_key'),
        ('kitchen_order', 'guest_email'),
        ('kitchen_orderitem', 'food_name'),
    ]
    column_status = {}
    for table, col in columns_to_check:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                    [table, col]
                )
                exists = cursor.fetchone()[0] > 0
                column_status[f'{table}.{col}'] = 'OK' if exists else 'MISSING'
        except Exception as e:
            column_status[f'{table}.{col}'] = f'ERROR: {e}'
    results['columns'] = column_status

    # 4. Test session creation
    try:
        if not request.session.session_key:
            request.session.create()
        results['session'] = f'OK (key={request.session.session_key})'
    except Exception as e:
        results['session'] = f'ERROR: {e}\n{traceback.format_exc()}'

    # 5. Test cart creation
    try:
        cart = get_or_create_cart(request)
        results['cart'] = f'OK (cart id={cart.id})'
    except Exception as e:
        results['cart'] = f'ERROR: {e}\n{traceback.format_exc()}'

    # 6. Option groups
    try:
        og_count = OptionGroup.objects.count()
        oc_count = OptionChoice.objects.count()
        results['option_groups'] = f'{og_count} groups, {oc_count} choices'
    except Exception as e:
        results['option_groups'] = f'ERROR: {e}'

    import json as json_lib
    html = '<html><body><pre style="font-family:monospace;font-size:14px;">'
    html += 'YAJU\'S KITCHEN — DATABASE DIAGNOSTIC\n'
    html += '=' * 60 + '\n'
    html += json_lib.dumps(results, indent=2)
    html += '\n' + '=' * 60
    html += '</pre></body></html>'
    return HttpResponse(html)


def fix_db_web(request):
    """
    Browser-accessible DB repair endpoint.
    Visit: /fix-db/?key=yajus2024
    Runs all schema repairs + seeds data. Safe to call multiple times.
    """
    # Simple key check to prevent accidental triggers
    if request.GET.get('key') != 'yajus2024':
        return HttpResponse(
            '<h2>Access denied.</h2><p>Add <code>?key=yajus2024</code> to the URL.</p>',
            status=403
        )

    log = []

    def ok(msg):
        log.append(f'✅ {msg}')

    def err(msg):
        log.append(f'❌ {msg}')

    def info(msg):
        log.append(f'ℹ️  {msg}')

    # Helpers to avoid Django's atomic get_or_create which uses SAVEPOINTs (problematic on TiDB)
    def safe_get_or_create_group(name):
        try:
            return OptionGroup.objects.get(name=name), False
        except OptionGroup.DoesNotExist:
            return OptionGroup.objects.create(name=name), True

    def safe_get_or_create_choice(group, name, delta):
        try:
            return OptionChoice.objects.get(group=group, name=name), False
        except OptionChoice.DoesNotExist:
            return OptionChoice.objects.create(group=group, name=name, price_delta=delta), True

    def safe_get_or_create_food_option(food, group):
        try:
            return FoodItemOption.objects.get(food=food, group=group), False
        except FoodItemOption.DoesNotExist:
            return FoodItemOption.objects.create(food=food, group=group), True

    # ── 1. Raw SQL repairs ────────────────────────────────────────
    REPAIRS = [
        ("django_session table", """
            CREATE TABLE IF NOT EXISTS django_session (
                session_key VARCHAR(40) NOT NULL PRIMARY KEY,
                session_data LONGTEXT NOT NULL,
                expire_date DATETIME(6) NOT NULL
            )
        """),
        ("django_session index", """
            CREATE INDEX IF NOT EXISTS ds_expire_idx ON django_session (expire_date)
        """),
        ("kitchen_cartitem_selected_options", """
            CREATE TABLE IF NOT EXISTS kitchen_cartitem_selected_options (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                cartitem_id BIGINT NOT NULL,
                optionchoice_id BIGINT NOT NULL,
                UNIQUE KEY uniq_ci (cartitem_id, optionchoice_id)
            )
        """),
        ("kitchen_orderitem_selected_options", """
            CREATE TABLE IF NOT EXISTS kitchen_orderitem_selected_options (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                orderitem_id BIGINT NOT NULL,
                optionchoice_id BIGINT NOT NULL,
                UNIQUE KEY uniq_oi (orderitem_id, optionchoice_id)
            )
        """),
        ("optionchoice.group_id",
         "ALTER TABLE kitchen_optionchoice ADD COLUMN IF NOT EXISTS group_id BIGINT NOT NULL DEFAULT 0"),
        ("optionchoice.price_delta",
         "ALTER TABLE kitchen_optionchoice ADD COLUMN IF NOT EXISTS price_delta DECIMAL(8,2) NOT NULL DEFAULT 0.00"),
        ("cart.session_key",
         "ALTER TABLE kitchen_cart ADD COLUMN IF NOT EXISTS session_key VARCHAR(40) NULL"),
        ("cart.updated_at",
         "ALTER TABLE kitchen_cart ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT NOW()"),
        ("order.guest_name",
         "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_name VARCHAR(100) NOT NULL DEFAULT ''"),
        ("order.guest_email",
         "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_email VARCHAR(254) NOT NULL DEFAULT ''"),
        ("order.guest_phone",
         "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_phone VARCHAR(20) NOT NULL DEFAULT ''"),
        ("order.delivery_address",
         "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS delivery_address TEXT"),
        ("order.special_instructions",
         "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS special_instructions TEXT"),
        ("order.updated_at",
         "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT NOW()"),
        ("orderitem.food_name",
         "ALTER TABLE kitchen_orderitem ADD COLUMN IF NOT EXISTS food_name VARCHAR(150) NOT NULL DEFAULT ''"),
        ("orderitem.food_price",
         "ALTER TABLE kitchen_orderitem ADD COLUMN IF NOT EXISTS food_price DECIMAL(10,2) NOT NULL DEFAULT 0.00"),
    ]

    try:
        with connection.cursor() as cursor:
            for label, sql in REPAIRS:
                try:
                    cursor.execute(sql)
                    ok(label)
                except Exception as e:
                    err(f'{label}: {e}')
    finally:
        # Close connection to force a fresh connection for the ORM block
        connection.close()

    # ── 2. Seed option groups ─────────────────────────────────────
    try:
        from kitchen.models import OptionGroup, OptionChoice, FoodItemOption, FoodItem as FI

        GROUPS = {
            'Spice Level': [
                ('Mild', 0), ('Medium', 0), ('Hot', 0), ('Extra Hot', 0),
            ],
            'Protein Add-On': [
                ('Extra Chicken', 500), ('Extra Beef', 500),
                ('Extra Fish', 600), ('Extra Prawns', 700),
            ],
            'Extra Sides': [
                ('Plantain', 300), ('Coleslaw', 200),
                ('Moi Moi', 400), ('Extra Sauce', 150),
            ],
        }
        groups = {}
        for gname, choices in GROUPS.items():
            grp, _ = safe_get_or_create_group(gname)
            groups[gname] = grp
            for cname, delta in choices:
                safe_get_or_create_choice(grp, cname, delta)
        ok(f'Option groups: {OptionGroup.objects.count()} groups, {OptionChoice.objects.count()} choices')

        RICE_SOUP_GRILL = {
            'Smoky Party Jollof Rice', 'Special Fried Rice',
            'Efo Riro Native Soup', 'Egusi Soup', 'Spiced Suya Platter',
        }
        for food in FI.objects.all():
            safe_get_or_create_food_option(food, groups['Spice Level'])
            if food.name in RICE_SOUP_GRILL:
                safe_get_or_create_food_option(food, groups['Protein Add-On'])
                safe_get_or_create_food_option(food, groups['Extra Sides'])
        ok(f'FoodItemOption links: {FoodItemOption.objects.count()} total')

    except Exception as e:
        err(f'Seeding: {e}\n{traceback.format_exc()}')
    finally:
        # Close connection again before session operations
        connection.close()

    # ── 3. Test session ───────────────────────────────────────────
    try:
        if not request.session.session_key:
            request.session.create()
        ok(f'Session working (key={request.session.session_key})')
    except Exception as e:
        err(f'Session: {e}')
    finally:
        connection.close()

    # ── 4. Test cart ──────────────────────────────────────────────
    try:
        cart = get_or_create_cart(request)
        ok(f'Cart working (id={cart.id})')
    except Exception as e:
        err(f'Cart: {e}\n{traceback.format_exc()}')
    finally:
        connection.close()

    # ── 5. Verification summary ───────────────────────────────────
    info('--- VERIFICATION ---')
    checks = [
        ('django_session rows', 'SELECT COUNT(*) FROM django_session'),
        ('optionchoice group_id column',
         "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
         "AND TABLE_NAME='kitchen_optionchoice' AND COLUMN_NAME='group_id'"),
        ('option groups', 'SELECT COUNT(*) FROM kitchen_optiongroup'),
        ('option choices', 'SELECT COUNT(*) FROM kitchen_optionchoice'),
        ('food→option links', 'SELECT COUNT(*) FROM kitchen_fooditemoption'),
    ]
    try:
        with connection.cursor() as cursor:
            for label, sql in checks:
                try:
                    cursor.execute(sql)
                    count = cursor.fetchone()[0]
                    (ok if count > 0 else err)(f'{label} = {count}')
                except Exception as e:
                    err(f'{label}: {e}')
    except Exception as e:
        err(f'Verification query: {e}')
    finally:
        connection.close()


    # ── Render HTML result ────────────────────────────────────────
    lines_html = ''
    for line in log:
        color = '#22c55e' if line.startswith('✅') else ('#ef4444' if line.startswith('❌') else '#94a3b8')
        lines_html += f'<div style="color:{color};margin:4px 0;font-size:15px;">{line}</div>'

    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Yaju's Kitchen — DB Fix</title>
  <style>
    body {{font-family:monospace;background:#0f172a;color:#e2e8f0;padding:40px;}}
    h1 {{color:#f97316;}}
    .box {{background:#1e293b;border-radius:12px;padding:30px;max-width:700px;}}
    a {{color:#f97316;}}
  </style>
</head>
<body>
  <div class="box">
    <h1>🍳 Yaju's Kitchen — DB Repair</h1>
    {lines_html}
    <hr style="border-color:#334155;margin:24px 0;">
    <p>
      <a href="/menu/">→ Go to Menu</a> &nbsp;|&nbsp;
      <a href="/debug/">→ Run Diagnostic</a> &nbsp;|&nbsp;
      <a href="/fix-db/?key=yajus2024">→ Run Again</a>
    </p>
  </div>
</body>
</html>"""
    return HttpResponse(html)


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
    
    food_items = FoodItem.objects.filter(is_available=True).select_related('category').distinct()
    
    if selected_category_id:
        food_items = food_items.filter(category_id=selected_category_id)
        
    if search_query:
        food_items = food_items.filter(name__icontains=search_query).distinct()
        
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
    try:
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
    except Http404:
        raise
    except Exception as e:
        import traceback
        print(f"[food_detail_view ERROR] {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e)
        }, status=500)


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
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)

    try:
        food = get_object_or_404(FoodItem, id=food_id)
        cart = get_or_create_cart(request)

        # Get selected option IDs
        option_ids = request.POST.getlist('options')
        qty = max(1, int(request.POST.get('quantity', 1)))

        # Parse selected options
        choices = OptionChoice.objects.filter(id__in=option_ids)

        # Find if same item with EXACTLY the same options already exists in cart
        cart_items = cart.items.filter(food=food)
        target_item = None

        for item in cart_items:
            item_opt_ids = set(item.selected_options.values_list('id', flat=True))
            query_opt_ids = set(int(x) for x in option_ids if x)
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

        total_qty = sum(item.quantity for item in cart.items.all())
        return JsonResponse({
            'success': True,
            'message': f"Added {food.name} to cart!",
            'total_qty': total_qty
        })
    except Exception as e:
        import traceback
        print(f"[cart_add_view ERROR] {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


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
        
    # Calculate total
    total_price = 0
    for item in cart.items.all():
        base = item.food.base_price
        for opt in item.selected_options.all():
            base += opt.price_delta
        total_price += base * item.quantity
        
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        # Check if the user chose to create an account
        create_account = request.POST.get('create_account') == 'on'
        password = request.POST.get('password')
        
        user = None
        if request.user.is_authenticated:
            user = request.user
        elif create_account and email and password:
            # Register user
            if User.objects.filter(username=email).exists():
                messages.error(request, "An account with this email already exists.")
                return redirect('checkout')
            
            user = User.objects.create_user(username=email, email=email, password=password)
            login(request, user)
            
        # Create Order
        order = Order.objects.create(
            user=user,
            guest_name=name or '',
            guest_email=email or (user.email if user else ''),
            guest_phone=phone,
            order_number=f"YJ{timezone.now().strftime('%Y%m%d%H%M%S')}",
            total_amount=total_price,
            delivery_address=address,
        )
        
        # Create OrderItems
        for cart_item in cart.items.all():
            order_item = OrderItem.objects.create(
                order=order,
                food=cart_item.food,
                food_name=cart_item.food.name,
                food_price=cart_item.food.base_price,
                quantity=cart_item.quantity,
            )
            if cart_item.selected_options.exists():
                order_item.selected_options.set(cart_item.selected_options.all())
            
        # Redirect to payment setup page
        return redirect('payment_initialize', order_id=order.id)
        
    # For GET requests, prefill if authenticated
    prefill = {}
    if request.user.is_authenticated:
        prefill['email'] = request.user.email
        
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
    amount_kobo = int(order.total_amount * 100)
    reference = f"YJ_{order.id}_{int(timezone.now().timestamp())}"
    
    # Create or update Payment
    Payment.objects.update_or_create(
        order=order,
        defaults={
            'amount': order.total_amount,
            'reference': reference,
            'status': 'pending',
            'method': 'paystack'
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

            order.status = 'processing'
            order.save()

            # Clear Cart
            cart = get_or_create_cart(request)
            cart.items.all().delete()

            # Send confirmation emails
            send_order_confirmation_email(order)
            send_payment_confirmation_email(order)

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
                'amount': order.total_amount,
                'reference': reference,
                'method': 'paystack'
            }
        )
        
        if action == 'success':
            payment.status = 'success'
            payment.save()

            order.status = 'processing'
            order.save()

            # Clear Cart
            cart = get_or_create_cart(request)
            cart.items.all().delete()

            messages.success(request, "Mock payment approved! Order is now being prepared.")
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
    Customer dashboard displaying orders.
    """
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
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
                    if item.selected_options.exists():
                        cart_item.selected_options.set(item.selected_options.all())
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
