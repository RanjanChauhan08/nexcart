import uuid

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models


def generate_tracking_code():
    return f"NC{uuid.uuid4().hex[:10].upper()}"


class Profile(models.Model):
    ROLE_CHOICES = [
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='buyer')
    city = models.CharField(max_length=100, blank=True)
    email_verified = models.BooleanField(default=False)
    store_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('phone', 'Phones'),
        ('laptop', 'Laptops'),
        ('earbuds', 'Earbuds'),
        ('tablet', 'Tablets'),
    ]

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='phone')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(max_length=1024, blank=True, null=True, help_text="Enter the URL of the product image.")
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = [
        ('placed', 'Order placed'),
        ('confirmed', 'Confirmed'),
        ('packed', 'Packed'),
        ('picked_up', 'Picked up'),
        ('origin_hub', 'At origin hub'),
        ('in_transit', 'In transit'),
        ('destination_hub', 'At destination hub'),
        ('out_for_delivery', 'Out for delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled by seller'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='seller_orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    customer_name = models.CharField(max_length=150, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_postal_code = models.CharField(max_length=6, blank=True)
    tracking_code = models.CharField(max_length=12, unique=True, default=generate_tracking_code, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='placed')
    current_location = models.CharField(max_length=150, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, default='cod')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.tracking_code}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)


class TrackingUpdate(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tracking_updates')
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    location = models.CharField(max_length=150)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Contact(models.Model):
    name = models.CharField(max_length=122)
    email = models.EmailField(max_length=122)
    # Add a validator to ensure the phone number consists of 10 digits.
    phnumber = models.CharField(
        max_length=10,
        validators=[RegexValidator(r'^\d{10}$', 'Enter a valid 10-digit phone number.')]
    )
    reason_for_contacting = models.TextField()

    def __str__(self):
        return self.name


class ServiceBooking(models.Model):
    DEVICE_CHOICES = [
        ('phone', 'Phone'),
        ('tablet', 'Tablet'),
        ('earbuds', 'Earbuds'),
        ('laptop', 'Laptop'),
    ]

    customer_name = models.CharField(max_length=150, blank=True)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=15)
    customer_location = models.CharField(max_length=255)
    device_type = models.CharField(max_length=10, choices=DEVICE_CHOICES)
    device_model = models.CharField(max_length=100)
    problems = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device_type} - {self.device_model}"
