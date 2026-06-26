import json
from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Avg, Sum, Count
from django.db.models.functions import ExtractHour, TruncDate
from django.shortcuts import render
from django.urls import path
from django.utils import timezone
from datetime import timedelta

from .models import (
    Profile, Category, FoodItem, OptionGroup, OptionChoice,
    FoodItemOption, Cart, CartItem, Order, OrderItem, Payment, Review
)

admin.site.site_header = "Yaju's Kitchen Admin"
admin.site.site_title = "Yaju's Kitchen Admin"
admin.site.index_title = "Operations Dashboard"

# Inline models for better management experience

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'


class OptionChoiceInline(admin.TabularInline):
    model = OptionChoice
    extra = 1


class FoodItemOptionInline(admin.TabularInline):
    model = FoodItemOption
    extra = 1


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('food_name', 'quantity', 'unit_price', 'options_summary')
    can_delete = False


class PaymentInline(admin.StackedInline):
    model = Payment
    can_delete = False
    readonly_fields = ('provider', 'amount', 'reference', 'status', 'created_at')


# Custom ModelAdmins

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'is_available', 'stock_status_display', 'track_stock')
    list_filter = ('category', 'is_available', 'track_stock')
    search_fields = ('name', 'description')
    inlines = [FoodItemOptionInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'category', 'description', 'base_price', 'image', 'is_available')
        }),
        ('Stock Management', {
            'fields': ('track_stock', 'stock_quantity', 'low_stock_threshold'),
            'description': 'Configure inventory tracking and stock levels'
        }),
    )

    def stock_status_display(self, obj):
        """Display colored stock status"""
        status = obj.stock_status
        if "Out of Stock" in status:
            return f'�� {status}'
        elif "Low Stock" in status:
            return f'�� {status}'
        elif "Not Tracked" in status:
            return f'⚪ {status}'
        return f'�� {status}'
    stock_status_display.short_description = 'Stock Status'


@admin.register(OptionGroup)
class OptionGroupAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [OptionChoiceInline]


@admin.register(OptionChoice)
class OptionChoiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'price_delta')
    list_filter = ('group',)
    search_fields = ('name',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'created_at', 'total_price')
    readonly_fields = ('created_at',)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'food', 'quantity', 'total_price')


# Order Export Admin Action
def export_orders_to_csv(modeladmin, request, queryset):
    """Export selected orders to CSV"""
    import csv
    from io import StringIO
    from django.http import HttpResponse
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'Order ID', 'Date', 'Customer', 'Email', 'Phone',
        'Status', 'Total', 'Items', 'Delivery Address'
    ])
    
    # Data rows
    for order in queryset:
        items_summary = '; '.join([
            f"{item.quantity}x {item.food_name}" 
            for item in order.items.all()
        ])
        
        writer.writerow([
            order.id,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            order.user.username if order.user else 'Guest',
            order.email,
            order.phone,
            order.get_status_display(),
            order.total,
            items_summary,
            order.delivery_address.replace('\n', ' ')
        ])
    
    # Create response
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="orders_export_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    
    return response

export_orders_to_csv.short_description = "Export selected orders to CSV"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'email', 'phone', 'status', 'total', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'email', 'phone', 'delivery_address')
    inlines = [OrderItemInline, PaymentInline]
    list_editable = ('status',)
    actions = [export_orders_to_csv]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'food', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('comment', 'food__name', 'user__username')


# 4. User & Profile Management

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('phone', 'address')


@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    inlines = [ProfileInline]
    readonly_fields = ('date_joined', 'last_login')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'address_preview')
    search_fields = ('user__username', 'user__email', 'phone')

    def address_preview(self, obj):
        return obj.address[:50] + '...' if len(obj.address) > 50 else obj.address
    address_preview.short_description = 'Address'


# 3. Analytics Proxy Model and ModelAdmin

class OrderAnalytics(Order):
    class Meta:
        proxy = True
        verbose_name = "Sales Analytics & Metrics"
        verbose_name_plural = "Sales Analytics & Metrics"


@admin.register(OrderAnalytics)
class OrderAnalyticsAdmin(admin.ModelAdmin):
    change_list_template = 'admin/analytics.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_site.admin_view(self.analytics_view), name='admin_analytics'),
        ]
        return custom_urls + urls

    def analytics_view(self, request):
        """Custom analytics view accessible via URL"""
        return self.changelist_view(request)

    def changelist_view(self, request, extra_context=None):
        # We only calculate analytics for orders that are successful (i.e. not cancelled, and have success payment)
        successful_orders = Order.objects.filter(payment__status='success')
        
        # 1. High Level KPIs
        order_count = successful_orders.count()
        total_revenue = successful_orders.aggregate(total=Sum('total'))['total'] or 0
        aov = successful_orders.aggregate(avg=Avg('total'))['avg'] or 0
        
        # 2. Top Selling Food Items
        top_foods = (
            OrderItem.objects.filter(order__payment__status='success')
            .values('food_name')
            .annotate(total_qty=Sum('quantity'), total_sales=Sum('quantity') * Avg('unit_price'))
            .order_by('-total_qty')[:5]
        )
        
        # Convert Decimals to float for chart JSON compatibility
        top_foods_labels = [item['food_name'] for item in top_foods]
        top_foods_data = [int(item['total_qty']) for item in top_foods]
        
        # 3. Hourly Sales Peaks (Grouped by hour of the day)
        hourly_data = (
            successful_orders.annotate(hour=ExtractHour('created_at'))
            .values('hour')
            .annotate(count=Count('id'), sales=Sum('total'))
            .order_by('hour')
        )
        
        # Fill in all 24 hours to ensure continuous chart line
        hourly_sales_map = {h: 0.0 for h in range(24)}
        for item in hourly_data:
            hour = item['hour']
            if hour is not None:
                hourly_sales_map[int(hour)] = float(item['sales'] or 0)
                
        hourly_labels = [f"{h:02d}:00" for h in range(24)]
        hourly_sales = [hourly_sales_map[h] for h in range(24)]
        
        # 4. Daily Sales Metrics (Last 7 Days)
        seven_days_ago = timezone.now().date() - timedelta(days=6)
        daily_data = (
            successful_orders.filter(created_at__date__gte=seven_days_ago)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(sales=Sum('total'))
            .order_by('date')
        )
        
        daily_sales_map = {seven_days_ago + timedelta(days=i): 0.0 for i in range(7)}
        for item in daily_data:
            date = item['date']
            if date is not None:
                daily_sales_map[date] = float(item['sales'] or 0)
                
        daily_labels = [date.strftime('%b %d') for date in sorted(daily_sales_map.keys())]
        daily_sales = [daily_sales_map[date] for date in sorted(daily_sales_map.keys())]
        
        # Extra Context variables
        extra_context = extra_context or {}
        extra_context.update({
            'title': 'Sales Summary & Analytics Dashboard',
            'order export to CSV/Excel','status':'pending','id':'7','priority':'low'},]}