# Yaju’s Kitchen: System Architecture & Design

## 1. Database & Relationships (Django ORM)

**User/Profile:** Leverage Django’s built-in `User` for authentication and attach a OneToOne `Profile` model for extra data (address, phone, preferences).  A OneToOneField is the standard way to extend the user model. For example: 
```python
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    # ... other fields ...
```
This keeps auth fields in Django’s `auth_user` and custom fields separate, avoiding conflicts. 

**Categories & Food Items:** Each `FoodItem` (menu dish) has a ForeignKey to a `Category` (e.g. *Pizza*, *Salad*). Categories can be flat or hierarchical as needed. Example:
```python
class Category(models.Model):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    # ... 

class FoodItem(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    description = models.TextField()
    base_price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='menu/')
    # Optional: a default spice level or vegetarian flag
```
This normalizes menu data; one category **has many** food items.

**Dynamic Customizability:** For extras (e.g. *Extra cheese*, *Spice level*), create separate models. For instance, an `OptionGroup` (e.g. “Toppings”, “Spice Level”) and `OptionChoice` (e.g. “Pepperoni”, “Mild”, “Hot”):
```python
class OptionGroup(models.Model):
    name = models.CharField(max_length=50)

class OptionChoice(models.Model):
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE, related_name='choices')
    name = models.CharField(max_length=50)
    price_delta = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)

class FoodItemOption(models.Model):
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='options')
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE)
    # This links which options apply to which food.
```
This allows many-to-many-like relations via through models: each `FoodItemOption` ties a dish to a group of choices. In an `OrderItem` or `CartItem`, you could then record which `OptionChoice` were selected. This keeps the schema normalized and extensible.

**Cart & CartItems:** Implement a `Cart` model for each user (or session), and a related `CartItem` with FK to `Cart` and `FoodItem`. For example:
```python
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # optional fields: session key, status, etc.

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)  # snapshot of price
    # optional: link to OptionChoices for this item
```
Each CartItem **belongs to one** Cart and one FoodItem, with a quantity and unit price stored. The Cart belongs to a User or is session-based for guests. This matches the common pattern (one cart, many cart items).

**Orders & OrderItems:** Once an order is placed, use an `Order` model (FK to User, status, total, timestamps) and `OrderItem` model (FK to Order and FoodItem).  Example:
```python
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('received','Received'),('preparing','Preparing'), ...])
    total = models.DecimalField(max_digits=10, decimal_places=2)
    # billing/shipping info fields

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    food = models.ForeignKey(FoodItem, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)  # price at purchase
    # Maybe store selected options here (JSONField or separate OptionChoices)
```
Note: Orders have **one-to-many** with OrderItems (not ManyToMany) because each item is unique to that order. Store the item price at time of purchase (unit_price) so historical reports are accurate even if menu prices change.

**Payments:** Create a `Payment` model linked to an Order, storing transaction ID, status, amount, timestamp. Use ForeignKey from Payment to Order:
```python
class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    provider = models.CharField(max_length=20)  # e.g. 'Paystack'
    status = models.CharField(max_length=20)   # e.g. 'pending', 'success', 'failed'
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)  # from gateway
    created_at = models.DateTimeField(auto_now_add=True)
```
Use OneToOne if each order has a single payment attempt.

**Reviews:** Finally, allow users to review `FoodItem`s. A `Review` model can have ForeignKeys to User and FoodItem, with rating (e.g. Integer 1–5) and comment. E.g.:
```python
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()  # e.g. 1-5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```
Optionally enforce one review per user per item or order. This relational design covers all entities, with clear OneToOne/ForeignKey links and some ManyToMany logic for custom options.

## 2. UI/UX Layout & Wireframing

**Layout Structure:** Use semantic HTML5 (e.g. `<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`). On desktop, a horizontal nav bar at top (logo, menu links, cart icon) and a two-column layout (filter sidebar + menu grid). On mobile, use a collapsible `<nav>` or hamburger menu, and one-column stacking. Forms (checkout, login) should be accessible via `<fieldset>` and `<button>`. For high-conversion, keep important CTA buttons (e.g. “Add to cart”, “Checkout”) prominently placed and color-distinct.

**Guest-to-Authenticated Checkout Flow:** 
1. *Cart Review:* User views cart and clicks “Checkout”.  
2. *Account Step:* Present options: “Continue as Guest” **prominently** (ideal labelling, e.g. “Checkout without account”), and “Sign In” / “Create Account” (less prominent). Baymard research stresses that making guest checkout *prominent* avoids drop-off.  
3. *Guest Flow:* If guest, ask for email/address/payment in one or two steps. Optionally offer to create an account *after* purchase.  
4. *Auth Flow:* If user signs in or registers, prefill known info.  
5. *Payment Step:* Securely collect payment details and submit. 

Throughout, clearly highlight progress (e.g. step indicators: Cart → Info → Payment → Confirm). Ensure “Guest Checkout” is clearly labeled to avoid confusion.

**Real-Time Cart Manipulation:** Users should see cart updates instantly. For example, when “Add to Cart” is clicked, update the cart badge count and total without full page reload (via AJAX or API call). On the Cart page, allow inline quantity adjustments (“+”/“–” buttons) and removal. NNGroup recommends that shopping carts display item details and make edits/removals easy. Provide a clear “Remove” icon and real-time subtotal calculation. If possible, show item thumbnails in the cart. Use a dedicated Cart page with all items listed (rather than a tiny overlay alone) so users can easily review before checkout.

**Order Status Tracking:** In the customer’s account or order confirmation page, show a timeline or status badges (e.g. Received → Preparing → Out for Delivery → Delivered). Use color-coding (e.g. active status in bold), and provide timestamps if available. For kitchen/staff dashboard, show incoming orders in a live-updating queue. 

- **Kitchen Staff View:** A dashboard (or even the same admin) listing open orders with current status. When staff advances an order status, broadcast update to the customer. 
- **Customer View:** A dynamic order detail page with a status indicator. 

To prevent users refreshing, updates should appear via WebSockets/AJAX as described below.

**Customizer UX:** Minimizing drop-off during customization (e.g. building a pizza) is crucial. Strategies include:
- **Visual Preview:** Show an image or interactive preview that updates as options are chosen.
- **Default Selections:** Pre-select common defaults (e.g. “Mild” spice) so user isn’t overwhelmed with empty choices.
- **Progressive Disclosure:** Reveal customization steps one at a time (e.g. first choose size, then toppings), with a progress indicator.
- **Inline Validation:** Immediately update price/availability when extras are toggled.
- **Save for Later:** Allow saving a partially customized item in cart to come back easily.

Keep the customizer UI clean (avoid clutter), label options clearly, and group related options (cheeses vs toppings). Possibly use tooltips or help icons for new users. The goal is a smooth, one-page customization that doesn’t require page reloads or hidden options.

## 3. Vanilla Frontend State Management & Performance

**File Architecture:** Organize vanilla JS and CSS in a component-ish structure. For example, create folders by feature or UI component: 
```
/static/css/
   base.css        /* global resets, typography */
   header.css
   menu.css
   cart.css
   customizer.css

/static/js/
   utils.js       /* utility functions, e.g. DOM helpers */
   cart.js        /* functions to add/remove/update cart items */
   menu.js        /* handlers for menu grid interactions */
   orderStatus.js /* handles WebSocket updates for order tracking */
```
Each JS file can encapsulate related logic (namespacing via modules or IIFEs if needed).  As one developer noted, grouping JS by app feature (Users, Cart, etc.) or by type (Views/Models) keeps things manageable. For example, `cart.js` might export an object `CartManager` with methods `addItem()`, `removeItem()`, `getTotal()`, etc. CSS can follow a BEM or utility-based naming (e.g. `.cart__item`, `.btn--primary`) for maintainability.

**Global State (Shopping Cart):** Without a framework, use a plain JS object or module to hold state. For instance, a `Cart` singleton object that maintains an array of items and totals. Update this in memory on add/remove. To persist across pages or sessions, sync to `localStorage` or cookies when items change (so guests keep their cart). Whenever cart state changes, emit a custom DOM event or call update functions that refresh the cart icon badge and mini-cart UI. Example pattern:
```js
const Cart = (function() {
  let items = JSON.parse(localStorage.getItem('cart')) || [];
  function save() { localStorage.setItem('cart', JSON.stringify(items)); }
  return {
    addItem(foodId, qty) { /* update items, call save() */ },
    removeItem(itemId) { /* ... */ },
    getTotal() { /* compute total from items */ },
    // dispatch a custom event or callback to update UI
  };
})();
```
This modular approach avoids globals littering. Use `window.dispatchEvent(new CustomEvent('cartUpdated', { detail: {...} }))` so any part of UI can listen and re-render badges or summaries. In short, keep a single source-of-truth object for cart state and trigger UI updates via events or observer pattern. This avoids repeated DOM queries and keeps logic in one place.

**Performance:** For UI, minimize DOM access by updating only changed parts (e.g. adjust quantity text and price cell rather than reloading entire table). Use `requestAnimationFrame` for smooth UI updates if doing animations. Defer heavy JS until needed. Use CSS animations/transitions sparingly (no frameworks means no Virtual DOM diffing, so optimize manual DOM changes).

For CSS, limit global rules. Organize CSS to use component classes (BEM-like), enabling easy overrides per page. Minify and bundle CSS/JS for production.

## 4. Real-Time Operations & Storage

**Live Order Tracking:** Use WebSockets via Django Channels for true real-time updates. When an order status changes (e.g. staff marks “Preparing” or “Out for Delivery”), have the backend trigger a Channels group message. For example, each Order could have a Channels group named like `order_{order.id}`, or simply use user-specific groups. In code:
```python
# In Django view or signal when status changes:
channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    f"order_{order.id}",
    {"type": "status_update", "status": order.status}
)
```
On the frontend, open a WebSocket to `ws://.../ws/orders/{order.id}/` and listen for `status_update`. Update the UI accordingly. The OneUptime guide shows using Channels `group_send` from Django views to notify clients.  This way, both the kitchen dashboard and the customer’s tracking page can instantly reflect status changes.

If WebSockets are too heavy, a fallback is polling an endpoint every few seconds, but Channels is preferred for prompt updates.

**Cloud Imagery & Delivery:** Store high-resolution images in a cloud media service. For example, use AWS S3 (with Django *django-storages*) or a specialized CDN like Cloudinary. These services can auto-generate optimized variants. On upload, images go to S3/Cloudinary (you might use Django signals or a REST API to handle uploads). In `FoodItem`, store the image URL or public ID. Serve images via a CDN domain for speed (CloudFront with S3, or Cloudinary’s own CDN).

On the frontend, use responsive `<img>` strategies: 
```html
<picture>
  <source media="(min-width:800px)" 
          srcset="{{ img_800w_url }} 800w, {{ img_1200w_url }} 1200w">
  <img src="{{ img_default_url }}" alt="..." loading="lazy" width="600" height="400">
</picture>
```
This uses `srcset` so the browser picks the best resolution for the viewport. Always include a default `src` and `loading="lazy"`. Modern browsers will lazy-load offscreen images without JS. Also consider next-gen formats (WebP/AVIF) if using Cloudinary or S3 + processing; serve those via `<source type="image/webp" ...>` in the `<picture>`. The above web.dev article shows that simply adding `loading="lazy"` defers offscreen images.

In summary: **Store** images in cloud (S3/Cloudinary), **deliver** through CDN, and use `<img srcset>` + `loading="lazy"` so that large images only load when needed. This provides both high quality and performance.

## 5. Payment API Architecture

**Transaction Flow (Paystack example):** 

1. **Initialize Payment:** User proceeds to pay. The frontend calls a Django view (or DRF endpoint) that creates a `Payment` record (status=`pending`, amount, order FK). The view calls Paystack’s initialize API (using secret key) with details: customer email, amount, callback URL, and a unique reference. Paystack returns an `authorization_url`.  
2. **Redirect:** The backend responds with this URL (or the frontend does), and the user is redirected to Paystack’s payment page to enter card details (or mobile money).  
3. **Payment Processing:** Paystack processes the payment. Meanwhile the user may complete, or abandon.  
4. **Verification & Callback:** If user completes and returns, Paystack hits your callback URL (as provided) or returns with a `reference` GET parameter. Your site calls Paystack’s “verify transaction” endpoint with the `reference` to confirm status. If successful, update `Payment.status='success'`, mark the `Order` as paid, send confirmation email, and empty the cart. (If unsuccessful, handle accordingly.)  

   **Fail-closed webhook:** To handle cases where the user never returns (browser closed), configure a Paystack webhook URL in your dashboard that points to your Django webhook endpoint. On a successful payment event, Paystack POSTs to your webhook with a signature header. Your Django view must verify this HMAC-SHA512 signature using your Paystack secret; if the signature check fails or missing, reject the webhook (fail-closed). Only upon valid signature do you update the order/payment in your database. This ensures payments aren’t recorded unless truly verified by Paystack. (This Django Paystack library notes: “Webhooks are rejected if no signing key can be resolved (fail closed)”.)

5. **Confirmation:** Once verification (via callback or webhook) is done, show the user a success page. Ensure idempotency so duplicate webhook calls don’t double-credit an order (track processed webhook IDs or use the Paystack client’s deduplication feature).

A similar flow applies for other gateways like Flutterwave. Always use HTTPS for webhook/callback, verify signatures, and only confirm orders after Paystack/Flutterwave confirms success. This **API-level flow**—initialize, redirect, verify, finalize—is the industry pattern for payment integration.

## 6. Admin Panel & Business Analytics

A Django **admin dashboard** can be customized to show sales metrics without building an entirely separate frontend. For example, use a proxy model or custom Admin `ModelAdmin` for orders/sales. Haki Benita demonstrates creating a “Sales Summary” proxy and overriding its `changelist_view` to aggregate data. In that example, the code queries the filtered queryset and annotates `Count` of orders and `Sum` of prices by category. The data (`summary = qs.values(...).annotate(...)`) is then passed to a custom admin template. This lets you show tables or charts alongside the normal admin UI.

**Metrics to include:** 
- **Average Order Value (AOV):** Compute via `Order.objects.aggregate(total=Sum('total'), count=Count('id'))`. AOV = total/count. Display as single number or chart. 
- **Top-selling Categories/Food:** Group `OrderItem` by `FoodItem.category` and sum quantities or totals to find which foods or categories sell most.
- **Hourly Sales Peaks:** Group orders by hour of `created_at` (use `extract_hour` in Django ORM) and sum totals to see which hours are busiest. This can feed a bar chart of sales vs hour.
- **Other KPIs:** Daily/weekly order counts, returning customers, etc.

In admin, you can embed charts by including e.g. Chart.js or using an admin-chart plugin. Haki’s solution involved extending the admin template to include a chart canvas under the summary table. Libraries like [django-admin-charts](https://github.com/ezhome/django-admin-charts) or a custom `<canvas>` with Chart.js can visualize these aggregates. Alternatively, create a custom admin view (`@staff_member_required` view) using Django templates to render any JS charts.

*Illustration:* a custom admin summary page might look like this: 

 *Example: A Django Admin “Sales Summary” page showing category totals and an hourly sales chart (source: hakibenita.com)*  

Overall, leverage Django Admin’s extensibility: add a new ModelAdmin for `SaleSummary` or `OrderSummary`, override `changelist_view` to provide analytics, and use a custom template to display tables and charts. This avoids extra tooling and keeps operations data alongside the familiar admin.

**Sources:** Best practices and patterns were informed by Django and UI/UX literature. These help guide the architecture, interactions, and security of the system.