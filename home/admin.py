from django.contrib import admin
from home.models import Contact, Order, OrderItem, Product, Profile, ServiceBooking, TrackingUpdate


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'store_name', 'city', 'email_verified')
    search_fields = ('user__username', 'user__email', 'store_name')
    list_filter = ('role', 'email_verified')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'category', 'price', 'stock', 'is_active')
    search_fields = ('name', 'description', 'seller__username')
    list_filter = ('category', 'is_active', 'seller')
    list_editable = ('price', 'stock', 'is_active')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_name', 'price', 'quantity')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('tracking_code', 'user', 'seller', 'status', 'total_amount', 'created_at')
    search_fields = ('tracking_code', 'user__username', 'seller__username', 'customer_name')
    list_filter = ('status', 'created_at')
    inlines = [OrderItemInline]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phnumber')


@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = ('customer_email', 'device_type', 'device_model', 'created_at')
    search_fields = ('customer_email', 'customer_phone', 'device_model')
    list_filter = ('device_type', 'created_at')
