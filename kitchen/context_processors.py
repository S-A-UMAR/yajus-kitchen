from .models import Cart

def get_or_create_cart(request):
    """
    Helper to get the current cart from the session or authenticated user.
    """
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            try:
                cart = Cart.objects.create(user=request.user)
            except Exception:
                cart = Cart.objects.get(user=request.user)
        # If there's an existing guest cart in the session, we can merge it
        session_cart_id = request.session.get('cart_id')
        if session_cart_id:
            try:
                session_cart = Cart.objects.get(id=session_cart_id, user__isnull=True)
                # Merge items
                for item in session_cart.items.all():
                    # Look if item already exists in user cart
                    existing_item = cart.items.filter(food=item.food).first()
                    if existing_item:
                        existing_item.quantity += item.quantity
                        existing_item.save()
                        # Transfer options
                        for opt in item.selected_options.all():
                            existing_item.selected_options.add(opt)
                        item.delete()
                    else:
                        item.cart = cart
                        item.save()
                session_cart.delete()
                del request.session['cart_id']
            except Cart.DoesNotExist:
                pass
        return cart
    else:
        # Session-based cart
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        cart_id = request.session.get('cart_id')
        
        if cart_id:
            try:
                cart = Cart.objects.get(id=cart_id)
            except Cart.DoesNotExist:
                cart = Cart.objects.create(session_key=session_key)
                request.session['cart_id'] = cart.id
        else:
            cart = Cart.objects.create(session_key=session_key)
            request.session['cart_id'] = cart.id
            
        return cart

def cart_processor(request):
    """
    Exposes the active cart and its items to all templates.
    """
    # Exclude system paths to avoid DB overhead and prevent crashes during admin use
    skip_prefixes = ('/admin/', '/accounts/', '/static/', '/media/')
    if any(request.path.startswith(p) for p in skip_prefixes):
        return {}
        
    try:
        cart = get_or_create_cart(request)
        # Use select_related and prefetch_related for efficiency
        cart_items = cart.items.select_related('food').prefetch_related('selected_options').all()
        
        total_qty = 0
        for item in cart_items:
            total_qty += item.quantity
        
        # Calculate total price without hitting the database multiple times
        total_price = 0
        for item in cart_items:
            option_deltas = 0
            for opt in item.selected_options.all():
                option_deltas += float(opt.price_delta)
            total_price += (float(item.food.base_price) + option_deltas) * item.quantity
        
        return {
            'cart': cart,
            'cart_items': cart_items,
            'cart_total_qty': total_qty,
            'cart_total_price': round(total_price, 2),
        }
    except Exception:
        # Fail gracefully if anything goes wrong
        return {
            'cart_total_qty': 0,
            'cart_total_price': 0,
        }
