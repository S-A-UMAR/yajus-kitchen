import csv
import json
from datetime import timedelta
from io import StringIO

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.http import HttpResponse
from django.utils import timezone

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
    Profile,
    Review,
)

admin.site.site_header = "Yaju's Kitchen Admin"
admin.site.site_title = "Yaju's Kitchen Admin"
admin.site.index_title = "Operations Dashboard"


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile"
    fields = ("phone", "address")


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
    readonly_fields = ("food_name", "quantity", "unit_price", "options_summary")


class PaymentInline(admin.StackedInline):
    model = Payment
    can_delete = False
    readonly_fields = ("provider", "amount", "reference", "status", "created_at")


def export_orders_to_csv(modeladmin, request, queryset):
    """Export selected orders to CSV."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Order ID",
            "Date",
            "Customer",
            "Email",
            "Phone",
            "Status",
            "Total",
            "Items",
            "Delivery Address",
        ]
    )

    for order in queryset.prefetch_related("items", "user"):
        items_summary = "; ".join(
            f"{item.quantity}x {item.food_name}" for item in order.items.all()
        )
        writer.writerow(
            [
                order.id,
                order.created_at.strftime("%Y-%m-%d %H:%M"),
                order.user.username if order.user else "Guest",
                order.email,
                order.phone,
                order.get_status_display(),
                order.total,
                items_summary,
                order.delivery_address.replace("\n", " "),
            ]
        )

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    response["Content-Disposition"] = (
        f'attachment; filename="orders_export_{timestamp}.csv"'
    )
    return response


export_orders_to_csv.short_description = "Export selected orders to CSV"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "base_price",
        "is_available",
        "stock_status_display",
        "track_stock",
    )
    list_filter = ("category", "is_available", "track_stock")
    search_fields = ("name", "description")
    inlines = [FoodItemOptionInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "category",
                    "description",
                    "base_price",
                    "image",
                    "is_available",
                )
            },
        ),
        (
            "Stock Management",
            {
                "fields": ("track_stock", "stock_quantity", "low_stock_threshold"),
                "description": "Configure inventory tracking and stock levels.",
            },
        ),
    )

    @admin.display(description="Stock Status")
    def stock_status_display(self, obj):
        if not obj.track_stock:
            return "Not tracked"
        if obj.stock_quantity == 0:
            return "Out of stock"
        if obj.is_low_stock:
            return f"Low stock ({obj.stock_quantity})"
        return f"In stock ({obj.stock_quantity})"


@admin.register(OptionGroup)
class OptionGroupAdmin(admin.ModelAdmin):
    list_display = ("name",)
    inlines = [OptionChoiceInline]


@admin.register(OptionChoice)
class OptionChoiceAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "price_delta")
    list_filter = ("group",)
    search_fields = ("name",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "created_at", "total_price")
    readonly_fields = ("created_at",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "food", "quantity", "total_price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "email", "phone", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "email", "phone", "delivery_address")
    inlines = [OrderItemInline, PaymentInline]
    list_editable = ("status",)
    actions = [export_orders_to_csv]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "food", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment", "food__name", "user__username")


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "date_joined")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "address_preview")
    search_fields = ("user__username", "user__email", "phone")

    @admin.display(description="Address")
    def address_preview(self, obj):
        return (
            obj.address[:50] + "..." if obj.address and len(obj.address) > 50 else obj.address
        )


class OrderAnalytics(Order):
    class Meta:
        proxy = True
        verbose_name = "Sales Analytics & Metrics"
        verbose_name_plural = "Sales Analytics & Metrics"


@admin.register(OrderAnalytics)
class OrderAnalyticsAdmin(admin.ModelAdmin):
    change_list_template = "admin/analytics.html"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        successful_orders = Order.objects.filter(payment__status="success")

        order_count = successful_orders.count()
        total_revenue = successful_orders.aggregate(total=Sum("total"))["total"] or 0
        aov = successful_orders.aggregate(avg=Avg("total"))["avg"] or 0

        top_foods = (
            OrderItem.objects.filter(order__payment__status="success")
            .values("food_name")
            .annotate(
                total_qty=Sum("quantity"),
                total_sales=Sum(F("quantity") * F("unit_price")),
            )
            .order_by("-total_qty")[:5]
        )

        top_foods_labels = [item["food_name"] for item in top_foods]
        top_foods_data = [int(item["total_qty"]) for item in top_foods]

        hourly_data = (
            successful_orders.annotate(hour=ExtractHour("created_at"))
            .values("hour")
            .annotate(count=Count("id"), sales=Sum("total"))
            .order_by("hour")
        )
        hourly_sales_map = {hour: 0.0 for hour in range(24)}
        for item in hourly_data:
            if item["hour"] is not None:
                hourly_sales_map[int(item["hour"])] = float(item["sales"] or 0)

        hourly_labels = [f"{hour:02d}:00" for hour in range(24)]
        hourly_sales = [hourly_sales_map[hour] for hour in range(24)]

        seven_days_ago = timezone.now().date() - timedelta(days=6)
        daily_data = (
            successful_orders.filter(created_at__date__gte=seven_days_ago)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(sales=Sum("total"))
            .order_by("date")
        )
        daily_sales_map = {
            seven_days_ago + timedelta(days=offset): 0.0 for offset in range(7)
        }
        for item in daily_data:
            if item["date"] is not None:
                daily_sales_map[item["date"]] = float(item["sales"] or 0)

        daily_labels = [
            current_date.strftime("%b %d") for current_date in sorted(daily_sales_map.keys())
        ]
        daily_sales = [
            daily_sales_map[current_date] for current_date in sorted(daily_sales_map.keys())
        ]

        extra_context = extra_context or {}
        extra_context.update(
            {
                "title": "Sales Summary & Analytics Dashboard",
                "order_count": order_count,
                "total_revenue": float(total_revenue),
                "aov": float(aov),
                "top_foods": top_foods,
                "top_foods_labels": json.dumps(top_foods_labels),
                "top_foods_data": json.dumps(top_foods_data),
                "hourly_labels": json.dumps(hourly_labels),
                "hourly_sales": json.dumps(hourly_sales),
                "daily_labels": json.dumps(daily_labels),
                "daily_sales": json.dumps(daily_sales),
            }
        )
        return super().changelist_view(request, extra_context=extra_context)
