from .models import Cart

def get_or_create_cart(request):
    """
    Helper to get the current cart from the session or authenticated user.
    """
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
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
    # Exclude admin and auth pages from running database checks to reduce overhead if necessary
    if request.path.startswith('/admin/'):
        return {}
        
    cart = get_or_create_cart(request)
    cart_items = cart.items.all().select_related('food').prefetch_related('selected_options')
    
    total_qty = sum(item.quantity for item in cart_items)
    
    return {
        'cart': cart,
        'cart_items': cart_items,
        'cart_total_qty': total_qty,
        'cart_total_price': cart.total_price,
    }
