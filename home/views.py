# --- Core Imports ---
import secrets
import uuid
import logging
import json
import re
from urllib.error import URLError
from urllib.request import urlopen
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from smtplib import SMTPException
from django.db import transaction
from django.utils import timezone
from django.shortcuts import render, redirect, HttpResponse
from django.http import JsonResponse
from django.urls import reverse
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

# --- Local Imports ---
# Import forms and models from the current application.
from .forms import ContactForm, ProductForm, ServiceBookingForm
from home.models import Order, OrderItem, Product, Profile, ServiceBooking, TrackingUpdate
from django.contrib import messages

# Get a logger instance for this module to log errors and other information.
logger = logging.getLogger(__name__)


# --- Authentication Views ---

def signup(request):
    """Handles new user registration for both buyers and sellers."""
    # If the user is already logged in, redirect them to the homepage.
    if request.user.is_authenticated:
        return redirect('home')

    # If the form is submitted (POST request).
    if request.method == 'POST':
        # Get form data, cleaning it up where necessary.
        email = request.POST.get('email', '').strip().lower()
        role = request.POST.get('role', 'buyer')
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        # --- Start of Validation Logic ---
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Enter a valid email address.')
        else:
            # Check if a user with this email already exists.
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, 'An account already exists with this email. Please log in.')
            # Ensure a valid role was selected.
            elif role not in {'buyer', 'seller'}:
                messages.error(request, 'Choose either Buyer or Seller.')
            # Check if passwords match.
            elif password != password_confirm:
                messages.error(request, 'The passwords do not match.')
            else:
                try:
                    # Use Django's built-in validators to check password strength.
                    validate_password(password)
                except ValidationError as error:
                    messages.error(request, ' '.join(error.messages))
                else:
                    # If all validation passes, send a verification email.
                    # The user's details are temporarily stored in the session.
                    if _send_email_code(request, email, 'signup', role, password_hash=make_password(password)):
                        return redirect('verify_email')
    # If it's a GET request or validation fails, render the signup page.
    return render(request, 'registration/signup.html')


def email_login(request):
    """Handles user login via email and password OR a one-time email code."""
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        action = request.POST.get('action', 'code')
        user = User.objects.filter(email__iexact=email).first()
        
        # Logic for password-based login.
        if action == 'password':
            if user and user.has_usable_password() and check_password(request.POST.get('password', ''), user.password):
                login(request, user)
                return redirect('home')
            messages.error(request, 'Incorrect email address or password. You can also sign in with an email code.')
        # Logic for email code-based login.
        elif user:
            if _send_email_code(request, email, 'login', user_id=user.id):
                return redirect('verify_email')
        else:
            messages.error(request, 'No NexCart account exists with that email. Please sign up first.')
            
    return render(request, 'registration/login.html')


def _send_email_code(request, email, purpose, role=None, user_id=None, password_hash=None):
    """A helper function to send a 6-digit verification code to a user's email."""
    # First, check if email settings are configured on the server.
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        # Log a detailed error for the admin, but show a generic message to the user.
        logger.error('Email verification is unavailable: SMTP credentials are not configured.')
        messages.error(request, 'We could not send a verification code right now. Please try again later.')
        return False

    # Generate a secure random 6-digit code.
    code = str(secrets.randbelow(900000) + 100000)
    
    # Store all necessary verification data in the user's session.
    # This includes the purpose (signup/login), user details, a hashed version of the code, and an expiration time.
    request.session['email_verification'] = {
        'email': email,
        'purpose': purpose,
        'role': role,
        'user_id': user_id,
        'password_hash': password_hash,
        'code_hash': make_password(code),
        'expires_at': (timezone.now() + timedelta(minutes=10)).isoformat(),
        'attempts': 0,
    }
    
    # Try to send the email.
    try:
        send_mail(
            'Your NexCart verification code',
            f'Your NexCart verification code is {code}. It expires in 10 minutes. Do not share this code.',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        messages.success(request, f'A verification code was sent to {email}.')
        return True
    # If sending fails, log the exception and inform the user.
    except (SMTPException, OSError):
        logger.exception('Unable to send %s verification code to %s.', purpose, email)
        request.session.pop('email_verification', None)
        messages.error(request, 'We could not send a verification code right now. Please try again later.')
        return False


def verify_email(request):
    """Handles the verification of the 6-digit code sent to the user's email."""
    # Retrieve the verification data from the session.
    verification = request.session.get('email_verification')
    
    # If there's no verification data, the user likely landed here by mistake.
    if not verification:
        messages.error(request, 'Start again by entering your email address.')
        return redirect('login')
        
    # Check if the code has expired.
    if timezone.now() > datetime.fromisoformat(verification['expires_at']):
        request.session.pop('email_verification', None)
        messages.error(request, 'Your verification code expired. Please request a new one.')
        return redirect('login' if verification['purpose'] == 'login' else 'signup')
        
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        
        # Limit the number of incorrect attempts to prevent brute-force attacks.
        verification['attempts'] += 1
        request.session['email_verification'] = verification
        if verification['attempts'] > 5:
            request.session.pop('email_verification', None)
            messages.error(request, 'Too many incorrect attempts. Please request a new code.')
            return redirect('login')
            
        # Securely check the provided code against the hashed version in the session.
        if not check_password(code, verification['code_hash']):
            messages.error(request, 'Incorrect verification code.')
        # If the code is correct and the purpose was 'signup'.
        elif verification['purpose'] == 'signup':
            email = verification['email']
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, 'An account already exists with this email. Please log in.')
                return redirect('login')
            # Create a new user and their profile.
            username = f"{email.split('@')[0][:120]}_{uuid.uuid4().hex[:8]}"
            user = User.objects.create(username=username, email=email)
            user.password = verification['password_hash']
            user.save(update_fields=['password'])
            user.profile.role = verification['role']
            user.profile.email_verified = True
            user.profile.save(update_fields=['role', 'email_verified'])
            # Clean up the session and log the new user in.
            request.session.pop('email_verification', None)
            login(request, user)
            return redirect('home')
        else:
            # If the code is correct and the purpose was 'login'.
            user = User.objects.filter(id=verification['user_id'], email__iexact=verification['email']).first()
            if not user:
                request.session.pop('email_verification', None)
                messages.error(request, 'Account not found. Please sign up again.')
                return redirect('signup')
            request.session.pop('email_verification', None)
            login(request, user)
            return redirect('home')
    return render(request, 'registration/verify_email.html', {'email': verification['email']})


# --- Decorators & Seller-Specific Views ---

# A custom decorator to ensure that only users with the 'seller' role can access a view.
def seller_required(view):
    @login_required
    def wrapped_view(request, *args, **kwargs):
        # Get or create a profile for the user to be safe.
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if profile.role != 'seller':
            raise PermissionDenied('Seller access only.')
        return view(request, *args, **kwargs)
    return wrapped_view


@seller_required
def seller_dashboard(request):
    """The main dashboard for sellers to manage their profile, products, and orders."""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Action: Update seller's city and store name.
        if action == 'save_location':
            request.user.profile.city = request.POST.get('city', '').strip()
            request.user.profile.store_name = request.POST.get('store_name', '').strip()
            request.user.profile.save(update_fields=['city', 'store_name'])
            messages.success(request, 'Your seller profile was updated.')
            return redirect('seller_dashboard')

        # Action: Update the tracking status of an order.
        if action == 'update_tracking':
            order = Order.objects.filter(id=request.POST.get('order_id'), seller=request.user).first()
            status = request.POST.get('status')
            location = request.POST.get('location', '').strip()
            note = request.POST.get('note', '').strip()
            valid_statuses = dict(Order.STATUS_CHOICES)
            shipment_statuses = [choice[0] for choice in Order.STATUS_CHOICES if choice[0] != 'cancelled']
            
            # Extensive validation to ensure the status update is valid.
            if (
                order and status in shipment_statuses and location
                and order.status not in {'cancelled', 'delivered'}
                and shipment_statuses.index(status) >= shipment_statuses.index(order.status)
            ):
                order.status = status
                order.current_location = location
                estimate = request.POST.get('estimated_delivery')
                if estimate:
                    order.estimated_delivery = estimate
                order.save(update_fields=['status', 'current_location', 'estimated_delivery'])
                TrackingUpdate.objects.create(order=order, status=status, location=location, note=note)
                messages.success(request, f'Tracking updated for {order.tracking_code}.')
            else:
                messages.error(request, 'Tracking can only move forward. Delivered or cancelled orders cannot be changed.')
            return redirect('seller_dashboard')

        # Action: Cancel an order.
        if action == 'cancel_order':
            # Use a database transaction to ensure atomicity. If any part fails, the whole operation is rolled back.
            with transaction.atomic():
                # Lock the order row to prevent race conditions.
                order = Order.objects.select_for_update().filter(
                    id=request.POST.get('order_id'), seller=request.user
                ).first()
                cancellable_statuses = {'placed', 'confirmed', 'packed'}
                reason = request.POST.get('cancellation_reason', '').strip()
                # Check if the order is in a state that allows cancellation.
                if order and order.status in cancellable_statuses:
                    order.status = 'cancelled'
                    order.current_location = order.current_location or request.user.profile.city or 'Seller dispatch centre'
                    order.cancellation_reason = reason or 'Cancelled by the seller before shipment.'
                    order.cancelled_at = timezone.now()
                    order.save(update_fields=['status', 'current_location', 'cancellation_reason', 'cancelled_at'])
                    for item in order.items.all():
                        # Return the items to stock.
                        if item.product:  # Product might be null if deleted
                            item.product.stock += item.quantity
                            item.product.save(update_fields=['stock'])
                    TrackingUpdate.objects.create(
                        order=order, status='cancelled', location=order.current_location,
                        note=order.cancellation_reason,
                    )
                    messages.success(request, f'Order {order.tracking_code} was cancelled and stock was restored.')
                else:
                    messages.error(request, 'Only orders that have not been picked up can be cancelled.')
            return redirect('seller_dashboard')

        # Action: Add a new product to the store.
        if action == 'publish_product':
            product_form = ProductForm(request.POST, request.FILES)
            if product_form.is_valid():
                product = product_form.save(commit=False)
                product.seller = request.user
                product.save()
                messages.success(request, 'Product published successfully.')
                return redirect('seller_dashboard')
            else:
                messages.error(request, 'Please correct the errors below.')

    product_form = ProductForm()
    # For a GET request, render the dashboard with the seller's products, orders, and a blank product form.
    return render(request, 'seller/dashboard.html', {
        'products': Product.objects.filter(seller=request.user),
        'seller_orders': Order.objects.filter(seller=request.user).prefetch_related('items__product'),
        'product_form': product_form,
    })


# --- Static Page & Contact Views ---

def index(request):
    """Renders the homepage."""
    return render(request,'home/index.html')
def about(request):
    """Renders the about page."""
    return render(request,'home/about.html')
def services(request):
    """Renders the main services page."""
    return render(request,'services/services.html')
def contact(request):
    """Handles the contact form submission."""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('ContactSend')
    else:
        form = ContactForm()
    return render(request,'home/contact.html', {'form': form})
def ContactSend(request):
    return render(request,"ContactSend.html")

# --- Service & Product Views ---

def book_service(request, device_type):
    """A single, dynamic view to handle service bookings for all device types (phone, laptop, etc.)."""
    # Validate that the device_type from the URL is a valid choice.
    if device_type not in dict(ServiceBooking.DEVICE_CHOICES):
        messages.error(request, "Invalid device type specified.")
        return redirect('services')

    if request.method == 'POST':
        form = ServiceBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.device_type = device_type
            booking.save()
            messages.success(request, "Service booked successfully!")
            return redirect("servicebooked")
    else:
        form = ServiceBookingForm(initial={'device_type': device_type})
    # Dynamically select the template based on the device type.
    template_name = f'services/{device_type}services.html'
    return render(request, template_name, {'form': form})

def buynow(request, category=None):
    """Displays a list of available products, optionally filtered by category."""
    # Start with all active, in-stock products.
    products = Product.objects.filter(is_active=True, stock__gt=0).select_related('seller__profile')
    # If a valid category is provided in the URL, filter the product list.
    if category and category in dict(Product.CATEGORY_CHOICES):
        products = products.filter(category=category)
    # Pass the products and category information to the template.
    return render(request, 'buynow/buynow.html', {
        'seller_products': products,
        'categories': Product.CATEGORY_CHOICES,
        'selected_category': category,
    })

# --- Cart & Checkout Views ---

def add_to_cart(request):
    """Adds a product to the shopping cart stored in the session."""
    if request.method == 'POST':
        # The cart is a dictionary: {product_id: quantity}.
        cart = request.session.get('cart', {})
        product_id = request.POST.get('product_id')
        if not product_id:
            messages.error(request, 'Select a product before adding it to your cart.')
            return redirect('buynow')

        try:
            # Ensure quantity is a positive integer.
            quantity = int(request.POST.get('quantity', 1))
            if quantity < 1:
                raise ValueError()
        except (ValueError, TypeError):
            quantity = 1

        # Check if the product exists and has enough stock.
        product = Product.objects.filter(id=product_id, is_active=True, stock__gte=quantity).first()
        if not product:
            # Check if the product exists but is out of stock for a better message.
            if Product.objects.filter(id=product_id).exists():
                messages.error(request, 'This product is currently out of stock or the requested quantity is not available.')
            else:
                messages.error(request, 'This product is no longer available.')
            return redirect('buynow')

        # Add the product to the cart or update its quantity.
        current_quantity = cart.get(product_id, 0)
        cart[product_id] = current_quantity + quantity

        request.session['cart'] = cart
        return redirect('checkout')
    return redirect('buynow')

def remove_from_cart(request, product_id):
    """Removes a product from the shopping cart."""
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    if product_id_str in cart:
        del cart[product_id_str]
        request.session['cart'] = cart
    return redirect('checkout')

def checkout(request):
    """Displays the contents of the cart and calculates the total price."""
    # Get cart data from the session.
    cart_data = request.session.get('cart', {})
    product_ids = cart_data.keys()
    # Fetch all product details from the database in a single query.
    products = Product.objects.filter(id__in=product_ids).select_related('seller__profile')
    
    cart_items = []
    total = Decimal('0')
    
    # Loop through the products and build a list of cart items with all necessary details for display.
    # This is more secure than trusting price data stored in the session.
    for product in products:
        quantity = cart_data.get(str(product.id), 0)
        if quantity > 0:
            item_total = product.price * quantity
            cart_items.append({
                'product_id': product.id,
                'name': product.name,
                'price': product.price,
                'quantity': quantity,
                'image': product.image.url if product.image else product.image_url,
                'seller_name': product.seller.profile.store_name or 'NexCart Seller',
                'item_total': item_total,
            })
            total += item_total
    return render(request, 'checkout/checkout.html', {'cart': cart_items, 'total': total})


def _lookup_indian_pin_code(postal_code):
    """A helper function to look up an Indian PIN code using an external API."""
    # Validate the PIN code format.
    if not re.fullmatch(r'\d{6}', postal_code):
        return None
    try:
        # Make the API call with a timeout.
        with urlopen(f'https://api.postalpincode.in/pincode/{postal_code}', timeout=4) as response:
            payload = json.load(response)
    # Handle potential network errors gracefully.
    except (URLError, TimeoutError, ValueError, OSError):
        return None
    if not payload or payload[0].get('Status') != 'Success':
        return None
    post_offices = payload[0].get('PostOffice') or []
    if not post_offices:
        return None
    # Extract and format the location details from the API response.
    office = post_offices[0]
    locality = office.get('Block') or office.get('District') or office.get('Name')
    district = office.get('District')
    state = office.get('State')
    city_parts = list(dict.fromkeys(part for part in (locality, district, state) if part))
    if not city_parts:
        return None
    return {'delivery_city': ', '.join(city_parts), 'locality': office.get('Name') or locality, 'state': state}


@login_required
def postal_code_lookup(request, postal_code):
    """An API endpoint for the frontend to validate a PIN code asynchronously."""
    details = _lookup_indian_pin_code(postal_code)
    if not details:
        return JsonResponse({'valid': False, 'message': 'Enter a valid Indian PIN code.'}, status=400)
    return JsonResponse({'valid': True, **details})

def place_order(request):
    """The main logic for creating an order from the items in the cart."""
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        postal_code = request.POST.get('postal_code', '').strip()
        address = request.POST.get('address', '').strip()
        customer_name = request.POST.get('name', '').strip()
        customer_phone = request.POST.get('phone', '').strip()
        # Temporarily disable PIN code lookup for PythonAnywhere free account
        # Free PythonAnywhere accounts have a whitelist of allowed external sites,
        # so this API call would likely fail.
        # pin_details = _lookup_indian_pin_code(postal_code)
        if not cart or not address or not postal_code or not customer_name or not customer_phone:
            messages.error(request, 'Add products and provide your name, phone number, street address and PIN code.')
            return redirect('checkout')
        if not re.fullmatch(r'\d{10}', customer_phone):
            messages.error(request, 'Enter a valid 10-digit phone number.')
            return redirect('checkout')
        # if not pin_details:
        #     messages.error(request, 'Enter a valid PIN code before placing your order.')
        #     return redirect('checkout')
        # delivery_city = pin_details['delivery_city']
        delivery_city = "Unknown City" # Placeholder
        delivery_address = f"{address}, {delivery_city} - {postal_code}"

        # Use a database transaction to ensure all order-related operations succeed or fail together.
        with transaction.atomic():
            # Re-read every product and price from the database. Session cart
            # values are display data only and must never decide an order total.
            product_ids = cart.keys()
            # Lock the product rows to prevent stock issues from concurrent requests.
            products_in_db = Product.objects.select_for_update().filter(
                id__in=product_ids, is_active=True
            ).select_related('seller__profile')

            products_map = {str(p.id): p for p in products_in_db}
            grouped_items = {} # {seller_id: [{'product': product, 'quantity': quantity}]}

            # Group cart items by seller.
            for product_id, quantity in cart.items():
                product = products_map.get(product_id)
                if not product or product.stock < quantity:
                    messages.error(request, f'Product "{product.name if product else "ID " + product_id}" is no longer available in the requested quantity. Please review your cart.')
                    return redirect('checkout')
                grouped_items.setdefault(product.seller_id, []).append({'product': product, 'quantity': quantity})

            orders = []
            # Create a separate order for each seller.
            for seller_id, item_details in grouped_items.items():
                total = sum((item['product'].price * item['quantity'] for item in item_details), Decimal('0'))
                seller = item_details[0]['product'].seller
                dispatch_city = seller.profile.city or 'Seller dispatch centre'
                order = Order.objects.create(
                    user=request.user,
                    seller=seller,
                    total_amount=total,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    delivery_address=delivery_address,
                    delivery_city=delivery_city,
                    delivery_postal_code=postal_code,
                    current_location=dispatch_city,
                    estimated_delivery=date.today() + timedelta(days=6),
                )
                TrackingUpdate.objects.create(
                    order=order, status='placed', location=dispatch_city,
                    note=f'Order received. Delivery destination: {delivery_city}.',
                )
                # Create OrderItem entries for each product in the order and decrement stock.
                for item in item_details:
                    product = item['product']
                    quantity = item['quantity']
                    product.stock -= quantity
                    product.save(update_fields=['stock'])
                    OrderItem.objects.create(
                        order=order, product=product, product_name=product.name, price=product.price, quantity=quantity
                    )
                orders.append(order)

        # Clear the cart from the session after the order is successfully placed.
        request.session['cart'] = []
        return render(request, 'checkout/order_success.html', {'orders': orders})
    return redirect('checkout')


# --- Order Tracking Views ---

@login_required
def my_orders(request):
    """Displays a list of all orders placed by the current user."""
    return render(request, 'tracking/my_orders.html', {
        'orders': Order.objects.filter(user=request.user).prefetch_related('items'),
    })


@login_required
def order_tracking(request, tracking_code):
    """Displays the detailed tracking information and timeline for a specific order."""
    order = Order.objects.filter(tracking_code=tracking_code, user=request.user).prefetch_related('items', 'tracking_updates').first()
    if not order:
        raise PermissionDenied('You cannot view this order.')
    status_keys = [choice[0] for choice in Order.STATUS_CHOICES if choice[0] != 'cancelled']
    last_shipment_update = order.tracking_updates.exclude(status='cancelled').order_by('-created_at').first()
    progress_status = last_shipment_update.status if order.status == 'cancelled' and last_shipment_update else order.status
    current_step = status_keys.index(progress_status)
    origin = order.seller.profile.city if order.seller and hasattr(order.seller, 'profile') and order.seller.profile.city else 'Seller dispatch centre'
    destination = order.delivery_city
    
    # Define the steps for the tracking timeline display.
    steps = [
        ('placed', 'Order placed', origin), ('confirmed', 'Seller confirmed', origin),
        ('packed', 'Packed and ready', origin), ('picked_up', 'Parcel picked up', origin),
        ('origin_hub', 'Arrived at origin hub', origin), ('in_transit', 'In transit', f'{origin} → {destination}'),
        ('destination_hub', 'Arrived at destination hub', destination),
        ('out_for_delivery', 'Out for delivery', destination), ('delivered', 'Delivered', destination),
    ]
    # Build the timeline data structure to be passed to the template.
    timeline = [
        {'status': status, 'label': label, 'location': location, 'complete': index <= current_step, 'current': index == current_step}
        for index, (status, label, location) in enumerate(steps)
    ]
    if order.status == 'cancelled':
        timeline.append({
            'status': 'cancelled', 'label': 'Order cancelled by seller',
            'location': order.current_location, 'complete': True, 'current': True,
        })
    return render(request, 'tracking/order_tracking.html', {
        'order': order, 'timeline': timeline, 'is_cancelled': order.status == 'cancelled',
    })
def servicebooked(request):
    """Renders a simple confirmation page after a service is booked."""
    return render(request,'services/servicebooked.html')
