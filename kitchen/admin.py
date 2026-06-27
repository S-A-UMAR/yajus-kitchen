from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

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

admin.site.site_header = "Yaju's Kitchen Admin"
admin.site.site_title = "Yaju's Kitchen Admin"
admin.site.index_title = "Operations Dashboard"


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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "base_price", "is_available")
    list_filter = ("category", "is_available")
    search_fields = ("name", "description")
    inlines = [FoodItemOptionInline]


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
    list_display = ("id", "user", "session_key", "created_at")
    readonly_fields = ("created_at",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "food", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "guest_email", "status", "total_amount", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "guest_email", "delivery_address")
    inlines = [OrderItemInline, PaymentInline]
    list_editable = ("status",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "food", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment", "food__name", "user__username")
