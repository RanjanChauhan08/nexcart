from django.contrib import admin
from django.urls import path,include
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from home import views
urlpatterns = [
    path('login/', views.email_login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('track/<str:tracking_code>/', views.order_tracking, name='order_tracking'),
    path('postal-code/<str:postal_code>/', views.postal_code_lookup, name='postal_code_lookup'),
    path('', login_required(views.index), name="home"),
    path('about', login_required(views.about), name="about"),
    path('services', login_required(views.services), name="services"),
    path('contact', login_required(views.contact), name="contact"),
    path('ContactSend', login_required(views.ContactSend), name="ContactSend"),
    path('phoneservices/', login_required(views.phoneservices), name="phoneservices"),
    path('laptopservices/', login_required(views.laptopservices), name="laptopservices"),
    path('earbudsservices/', login_required(views.earbudsservices), name="earbudsservices"),
    path('tabletservices/', login_required(views.tabletservices), name="tabletservices"),
    path('buynow', login_required(views.buynow), name="buynow"),
    path('buylaptop', login_required(views.buylaptop), name="buylaptop"),
    path('buytablet', login_required(views.buytablet), name="buytablet"),
    path('buyearbuds', login_required(views.buyearbuds), name="buyearbuds"),
    path('buyphone', login_required(views.buyphone), name="buyphone"),
    path('checkout', login_required(views.checkout), name="checkout"),
    path('add-to-cart', login_required(views.add_to_cart), name="add_to_cart"),
    path('remove-from-cart/<int:index>', login_required(views.remove_from_cart), name="remove_from_cart"),
    path('place-order', login_required(views.place_order), name="place_order"),
    path('servicebooked', login_required(views.servicebooked), name="servicebooked")
]
