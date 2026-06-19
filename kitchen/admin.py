import json
from django.contrib import admin
from django.db.models import Avg, Sum, Count
from django.db.models.functions import ExtractHour, TruncDate
from django.shortcuts import render
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
    list_display = ('name', 'category', 'base_price', 'is_available')
    list_filter = ('category', 'is_available')
    search_fields = ('name', 'description')
    inlines = [FoodItemOptionInline]


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


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'email', 'phone', 'status', 'total', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'email', 'phone', 'delivery_address')
    inlines = [OrderItemInline, PaymentInline]
    list_editable = ('status',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'food', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('comment', 'food__name', 'user__username')


# 3. Analytics Proxy Model and ModelAdmin

class OrderAnalytics(Order):
    class Meta:
        proxy = True
        verbose_name = "Sales Analytics & Metrics"
        verbose_name_plural = "Sales Analytics & Metrics"


@admin.register(OrderAnalytics)
class OrderAnalyticsAdmin(admin.ModelAdmin):
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
            'order_count': order_count,
            'total_revenue': float(total_revenue),
            'aov': float(aov),
            'top_foods': top_foods,
            'top_foods_labels': json.dumps(top_foods_labels),
            'top_foods_data': json.dumps(top_foods_data),
            'hourly_labels': json.dumps(hourly_labels),
            'hourly_sales': json.dumps(hourly_sales),
            'daily_labels': json.dumps(daily_labels),
            'daily_sales': json.dumps(daily_sales),
        })
        
        # Use our custom template which extends admin change_list template
        return render(request, 'admin/analytics.html', extra_context)
