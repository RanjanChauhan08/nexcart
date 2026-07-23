# --- Core Imports ---
from django.contrib import admin
from django.urls import path,include
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required

# --- Local Imports ---
from home import views

# This list defines all the URL patterns for the 'home' application.
urlpatterns = [
    # --- Authentication URLs ---
    path('login/', views.email_login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # --- Seller & Order Management URLs ---
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('track/<str:tracking_code>/', views.order_tracking, name='order_tracking'),

    # --- API-like URL for frontend JavaScript ---
    path('postal-code/<str:postal_code>/', views.postal_code_lookup, name='postal_code_lookup'),

    # --- Core Site Pages ---
    path('', views.index, name="home"),
    path('about', views.about, name="about"),
    path('services', views.services, name="services"),

    # --- Contact & Service Booking URLs ---
    path('contact', login_required(views.contact), name="contact"),
    path('ContactSend', login_required(views.ContactSend), name="ContactSend"),
    # A dynamic URL to handle booking for different device types (e.g., /services/phone/).
    path('services/<str:device_type>/', login_required(views.book_service), name="book_service"),

    # --- Product & Checkout Flow URLs ---
    # The main product listing page.
    path('buy/', views.buynow, name="buynow"),
    # A dynamic URL to show products filtered by category (e.g., /buy/laptop/).
    path('buy/<str:category>/', views.buynow, name="buynow_category"),
    path('checkout', login_required(views.checkout), name="checkout"),
    path('add-to-cart', login_required(views.add_to_cart), name="add_to_cart"),
    path('remove-from-cart/<int:product_id>', login_required(views.remove_from_cart), name="remove_from_cart"),
    path('place-order', login_required(views.place_order), name="place_order"),
    path('servicebooked', login_required(views.servicebooked), name="servicebooked")
]
