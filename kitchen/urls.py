from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Diagnostic — remove after fixing
    path('debug/', views.debug_view, name='debug'),

    # Customer Pages
    path('', views.home_view, name='home'),
    path('menu/', views.menu_view, name='menu'),
    path('menu/item/<int:food_id>/', views.food_detail_view, name='food_detail'),
    path('cart/', views.cart_view, name='cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('order/<int:order_id>/success/', views.order_success_view, name='order_success'),
    path('order/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('order/<int:order_id>/status/', views.order_status_api, name='order_status_api'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('contact/', views.contact_view, name='contact'),
    
    # Auth Pages
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Cart Ajax Actions
    path('cart/add/<int:food_id>/', views.cart_add_view, name='cart_add'),
    path('cart/update/<int:item_id>/', views.cart_update_view, name='cart_update'),
    path('cart/remove/<int:item_id>/', views.cart_remove_view, name='cart_remove'),
    path('cart/drawer/', views.cart_drawer_partial, name='cart_drawer_partial'),
    
    # Payment Actions
    path('payment/initialize/<int:order_id>/', views.payment_initialize_view, name='payment_initialize'),
    path('payment/callback/', views.payment_callback_view, name='payment_callback'),
    path('payment/webhook/', views.payment_webhook_view, name='payment_webhook'),
    path('payment/mock-checkout/<int:order_id>/', views.mock_checkout_view, name='mock_checkout'),
    
    # Review Actions
    path('review/add/<int:food_id>/', views.add_review_view, name='add_review'),
]
