from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

from .models import (
    Cart,
    CartItem,
    Category,
    FoodItem,
    FoodItemOption,
    OptionChoice,
    OptionGroup,
    Order,
    OrderItem,
    Payment,
    Review,
)


class YajuKitchenAdminSite(admin.AdminSite):
    site_header = "Yaju's Kitchen Admin"
    site_title = "Yaju's Kitchen Admin"
    index_title = "Operations Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("analytics/", self.admin_view(self.analytics_view), name="analytics"),
        ]
        return custom_urls + urls

    def analytics_view(self, request):
        # Get basic analytics
        total_orders = Order.objects.count()
        total_revenue = Order.objects.filter(status__in=["delivered", "received"]).aggregate(Sum("total_amount"))["total_amount__sum"] or 0
        total_users = User.objects.count()

        # Recent orders (last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_orders = Order.objects.filter(created_at__gte=seven_days_ago).order_by("-created_at")[:10]
        recent_orders_count = recent_orders.count()
        recent_revenue = recent_orders.filter(status__in=["delivered", "received"]).aggregate(Sum("total_amount"))["total_amount__sum"] or 0

        # Status breakdown
        status_counts = {}
        for status, _ in Order.STATUS_CHOICES:
            status_counts[status] = Order.objects.filter(status=status).count()

        context = {
            **self.each_context(request),
            "title": "Sales & Performance Analytics",
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "total_users": total_users,
            "recent_orders": recent_orders,
            "recent_orders_count": recent_orders_count,
            "recent_revenue": recent_revenue,
            "status_counts": status_counts,
        }
        return render(request, "admin/analytics.html", context)


# Initialize custom admin site
admin_site = YajuKitchenAdminSite(name="yaju_kitchen_admin")


class OptionChoiceInline(admin.TabularInline):
    model = OptionChoice
    extra = 1


class FoodItemOptionInline(admin.TabularInline):
    model = FoodItemOption
    extra = 1


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("food_name", "quantity", "food_price")


class PaymentInline(admin.StackedInline):
    model = Payment
    can_delete = False
    readonly_fields = ("method", "amount", "reference", "status", "created_at")


@admin.register(Category, site=admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(FoodItem, site=admin_site)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "base_price", "is_available")
    list_filter = ("category", "is_available")
    search_fields = ("name", "description")
    inlines = [FoodItemOptionInline]


@admin.register(OptionGroup, site=admin_site)
class OptionGroupAdmin(admin.ModelAdmin):
    list_display = ("name",)
    inlines = [OptionChoiceInline]


@admin.register(OptionChoice, site=admin_site)
class OptionChoiceAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "price_delta")
    list_filter = ("group",)
    search_fields = ("name",)


@admin.register(Cart, site=admin_site)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "created_at")
    readonly_fields = ("created_at",)


@admin.register(CartItem, site=admin_site)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "food", "quantity")


@admin.register(Order, site=admin_site)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "guest_email", "status", "total_amount", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "guest_email", "delivery_address")
    inlines = [OrderItemInline, PaymentInline]
    list_editable = ("status",)


@admin.register(Review, site=admin_site)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "food", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment", "food__name", "user__username")


# Register User to custom admin
admin_site.register(User, UserAdmin)
