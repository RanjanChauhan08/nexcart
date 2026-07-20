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

from .forms import ProductForm, ServiceBookingForm
from home.models import Order, OrderItem, Product, Profile, ServiceBooking, TrackingUpdate
from django.contrib import messages


logger = logging.getLogger(__name__)


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        role = request.POST.get('role', 'buyer')
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Enter a valid email address.')
        else:
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, 'An account already exists with this email. Please log in.')
            elif role not in {'buyer', 'seller'}:
                messages.error(request, 'Choose either Buyer or Seller.')
            elif password != password_confirm:
                messages.error(request, 'The passwords do not match.')
            else:
                try:
                    validate_password(password)
                except ValidationError as error:
                    messages.error(request, ' '.join(error.messages))
                else:
                    if _send_email_code(request, email, 'signup', role, password_hash=make_password(password)):
                        return redirect('verify_email')
    return render(request, 'registration/signup.html')


def email_login(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        action = request.POST.get('action', 'code')
        user = User.objects.filter(email__iexact=email).first()
        if action == 'password':
            if user and user.has_usable_password() and check_password(request.POST.get('password', ''), user.password):
                login(request, user)
                return redirect('home')
            messages.error(request, 'Incorrect email address or password. You can also sign in with an email code.')
        elif user:
            if _send_email_code(request, email, 'login', user_id=user.id):
                return redirect('verify_email')
        else:
            messages.error(request, 'No NexCart account exists with that email. Please sign up first.')
    return render(request, 'registration/login.html')


def _send_email_code(request, email, purpose, role=None, user_id=None, password_hash=None):
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        # Do not expose server configuration details to visitors. This must be
        # configured once by the site owner before verification can work.
        logger.error('Email verification is unavailable: SMTP credentials are not configured.')
        messages.error(request, 'We could not send a verification code right now. Please try again later.')
        return False

    code = str(secrets.randbelow(900000) + 100000)
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
    except (SMTPException, OSError):
        logger.exception('Unable to send %s verification code to %s.', purpose, email)
        request.session.pop('email_verification', None)
        messages.error(request, 'We could not send a verification code right now. Please try again later.')
        return False


def verify_email(request):
    verification = request.session.get('email_verification')
    if not verification:
        messages.error(request, 'Start again by entering your email address.')
        return redirect('login')
    if timezone.now() > datetime.fromisoformat(verification['expires_at']):
        request.session.pop('email_verification', None)
        messages.error(request, 'Your verification code expired. Please request a new one.')
        return redirect('login' if verification['purpose'] == 'login' else 'signup')
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        verification['attempts'] += 1
        request.session['email_verification'] = verification
        if verification['attempts'] > 5:
            request.session.pop('email_verification', None)
            messages.error(request, 'Too many incorrect attempts. Please request a new code.')
            return redirect('login')
        if not check_password(code, verification['code_hash']):
            messages.error(request, 'Incorrect verification code.')
        elif verification['purpose'] == 'signup':
            email = verification['email']
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, 'An account already exists with this email. Please log in.')
                return redirect('login')
            username = f"{email.split('@')[0][:120]}_{uuid.uuid4().hex[:8]}"
            user = User.objects.create(username=username, email=email)
            user.password = verification['password_hash']
            user.save(update_fields=['password'])
            user.profile.role = verification['role']
            user.profile.email_verified = True
            user.profile.save(update_fields=['role', 'email_verified'])
            request.session.pop('email_verification', None)
            login(request, user)
            return redirect('home')
        else:
            user = User.objects.filter(id=verification['user_id'], email__iexact=verification['email']).first()
            if not user:
                request.session.pop('email_verification', None)
                messages.error(request, 'Account not found. Please sign up again.')
                return redirect('signup')
            request.session.pop('email_verification', None)
            login(request, user)
            return redirect('home')
    return render(request, 'registration/verify_email.html', {'email': verification['email']})


def seller_required(view):
    @login_required
    def wrapped_view(request, *args, **kwargs):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if profile.role != 'seller':
            raise PermissionDenied('Seller access only.')
        return view(request, *args, **kwargs)
    return wrapped_view


@seller_required
def seller_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_location':
            request.user.profile.city = request.POST.get('city', '').strip()
            request.user.profile.store_name = request.POST.get('store_name', '').strip()
            request.user.profile.save(update_fields=['city', 'store_name'])
            messages.success(request, 'Your seller profile was updated.')
            return redirect('seller_dashboard')

        if action == 'update_tracking':
            order = Order.objects.filter(id=request.POST.get('order_id'), seller=request.user).first()
            status = request.POST.get('status')
            location = request.POST.get('location', '').strip()
            note = request.POST.get('note', '').strip()
            valid_statuses = dict(Order.STATUS_CHOICES)
            shipment_statuses = [choice[0] for choice in Order.STATUS_CHOICES if choice[0] != 'cancelled']
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

        if action == 'cancel_order':
            with transaction.atomic():
                order = Order.objects.select_for_update().filter(
                    id=request.POST.get('order_id'), seller=request.user
                ).first()
                cancellable_statuses = {'placed', 'confirmed', 'packed'}
                reason = request.POST.get('cancellation_reason', '').strip()
                if order and order.status in cancellable_statuses:
                    order.status = 'cancelled'
                    order.current_location = order.current_location or request.user.profile.city or 'Seller dispatch centre'
                    order.cancellation_reason = reason or 'Cancelled by the seller before shipment.'
                    order.cancelled_at = timezone.now()
                    order.save(update_fields=['status', 'current_location', 'cancellation_reason', 'cancelled_at'])
                    for item in order.items.all():
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

    return render(request, 'seller/dashboard.html', {
        'products': Product.objects.filter(seller=request.user),
        'seller_orders': Order.objects.filter(seller=request.user).prefetch_related('items__product'),
        'product_form': ProductForm(),
    })


def index(request):
    return render(request,'home/index.html')
def about(request):
    return render(request,'home/about.html')
def services(request):
    return render(request,'services/services.html')
from .forms import ContactForm, ServiceBookingForm
def contact(request):
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
def phoneservices(request):
    if request.method=='POST':
        form = ServiceBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.device_type = 'phone'
            booking.save()
            messages.success(request, "Service booked successfully!")
            return redirect("servicebooked")
    else:
        form = ServiceBookingForm(initial={'device_type': 'phone'})
    return render(request,'services/phoneservices.html', {'form': form})
def laptopservices(request):
    if request.method=='POST':
        form = ServiceBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.device_type = 'laptop'
            booking.save()
            messages.success(request, "Service booked successfully!")
            return redirect("servicebooked")
    else:
        form = ServiceBookingForm(initial={'device_type': 'laptop'})
    return render(request,"services/laptopservices.html", {'form': form})
def earbudsservices(request):
    if request.method=='POST':
        form = ServiceBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.device_type = 'earbuds'
            booking.save()
            messages.success(request, "Service booked successfully!")
            return redirect("servicebooked")
    else:
        form = ServiceBookingForm(initial={'device_type': 'earbuds'})
    return render(request,'services/earbudsservices.html', {'form': form})
def tabletservices(request):
    if request.method=='POST':
        form = ServiceBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.device_type = 'tablet'
            booking.save()
            messages.success(request, "Service booked successfully!")
            return redirect("servicebooked")
    else:
        form = ServiceBookingForm(initial={'device_type': 'tablet'})
    return render(request,'services/tabletservices.html', {'form': form})
def buynow(request):
    category = request.GET.get('category', '')
    products = Product.objects.filter(is_active=True, stock__gt=0).select_related('seller__profile')
    if category in dict(Product.CATEGORY_CHOICES):
        products = products.filter(category=category)
    else:
        category = ''
    return render(request, 'buynow/buynow.html', {
        'seller_products': products,
        'categories': Product.CATEGORY_CHOICES,
        'selected_category': category,
    })
def buyearbuds(request):
    return redirect(f"{reverse('buynow')}?category=earbuds")
def buyphone(request):
    return redirect(f"{reverse('buynow')}?category=phone")
def buytablet(request):
    return redirect(f"{reverse('buynow')}?category=tablet")
def buylaptop(request):
    return redirect(f"{reverse('buynow')}?category=laptop")

def add_to_cart(request):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        product_id = request.POST.get('product_id')
        if not product_id:
            messages.error(request, 'Select a product before adding it to your cart.')
            return redirect('buynow')

        try:
            quantity = int(request.POST.get('quantity', 1))
            if quantity < 1:
                raise ValueError()
        except (ValueError, TypeError):
            quantity = 1

        product = Product.objects.filter(id=product_id, is_active=True, stock__gte=quantity).first()
        if not product:
            messages.error(request, 'This product is no longer available.')
            return redirect('buynow')

        current_quantity = cart.get(product_id, 0)
        cart[product_id] = current_quantity + quantity

        request.session['cart'] = cart
        return redirect('checkout')
    return redirect('buynow')

def remove_from_cart(request, index):
    cart = request.session.get('cart', [])
    if 0 <= index < len(cart):
        cart.pop(index)
        request.session['cart'] = cart
    return redirect('checkout')

def checkout(request):
    cart_data = request.session.get('cart', {})
    product_ids = cart_data.keys()
    products = Product.objects.filter(id__in=product_ids).select_related('seller__profile')
    
    cart_items = []
    total = Decimal('0')
    
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
    """Return the canonical delivery locality for a six-digit Indian PIN."""
    if not re.fullmatch(r'\d{6}', postal_code):
        return None
    try:
        with urlopen(f'https://api.postalpincode.in/pincode/{postal_code}', timeout=4) as response:
            payload = json.load(response)
    except (URLError, TimeoutError, ValueError, OSError):
        return None
    if not payload or payload[0].get('Status') != 'Success':
        return None
    post_offices = payload[0].get('PostOffice') or []
    if not post_offices:
        return None
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
    details = _lookup_indian_pin_code(postal_code)
    if not details:
        return JsonResponse({'valid': False, 'message': 'Enter a valid Indian PIN code.'}, status=400)
    return JsonResponse({'valid': True, **details})

def place_order(request):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        postal_code = request.POST.get('postal_code', '').strip()
        address = request.POST.get('address', '').strip()
        customer_name = request.POST.get('name', '').strip()
        customer_phone = request.POST.get('phone', '').strip()
        pin_details = _lookup_indian_pin_code(postal_code)
        if not cart or not address or not postal_code or not customer_name or not customer_phone:
            messages.error(request, 'Add products and provide your name, phone number, street address and PIN code.')
            return redirect('checkout')
        if not re.fullmatch(r'\d{10}', customer_phone):
            messages.error(request, 'Enter a valid 10-digit phone number.')
            return redirect('checkout')
        if not pin_details:
            messages.error(request, 'Enter a valid PIN code before placing your order.')
            return redirect('checkout')
        delivery_city = pin_details['delivery_city']
        delivery_address = f"{address}, {delivery_city} - {postal_code}"

        with transaction.atomic():
            # Re-read every product and price from the database. Session cart
            # values are display data only and must never decide an order total.
            product_ids = cart.keys()
            products_in_db = Product.objects.select_for_update().filter(
                id__in=product_ids, is_active=True
            ).select_related('seller__profile')

            products_map = {str(p.id): p for p in products_in_db}
            grouped_items = {} # {seller_id: [{'product': product, 'quantity': quantity}]}

            for product_id, quantity in cart.items():
                product = products_map.get(product_id)
                if not product or product.stock < quantity:
                    messages.error(request, f'Product "{product.name if product else "ID " + product_id}" is no longer available in the requested quantity. Please review your cart.')
                    return redirect('checkout')
                grouped_items.setdefault(product.seller_id, []).append({'product': product, 'quantity': quantity})

            orders = []
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
                for item in item_details:
                    product = item['product']
                    quantity = item['quantity']
                    product.stock -= quantity
                    product.save(update_fields=['stock'])
                    OrderItem.objects.create(
                        order=order, product=product, product_name=product.name, price=product.price, quantity=quantity
                    )
                orders.append(order)

        request.session['cart'] = []
        return render(request, 'checkout/order_success.html', {'orders': orders})
    return redirect('checkout')


@login_required
def my_orders(request):
    return render(request, 'tracking/my_orders.html', {
        'orders': Order.objects.filter(user=request.user).prefetch_related('items'),
    })


@login_required
def order_tracking(request, tracking_code):
    order = Order.objects.filter(tracking_code=tracking_code, user=request.user).prefetch_related('items', 'tracking_updates').first()
    if not order:
        raise PermissionDenied('You cannot view this order.')
    status_keys = [choice[0] for choice in Order.STATUS_CHOICES if choice[0] != 'cancelled']
    last_shipment_update = order.tracking_updates.exclude(status='cancelled').order_by('-created_at').first()
    progress_status = last_shipment_update.status if order.status == 'cancelled' and last_shipment_update else order.status
    current_step = status_keys.index(progress_status)
    origin = order.seller.profile.city if order.seller and hasattr(order.seller, 'profile') and order.seller.profile.city else 'Seller dispatch centre'
    destination = order.delivery_city
    steps = [
        ('placed', 'Order placed', origin), ('confirmed', 'Seller confirmed', origin),
        ('packed', 'Packed and ready', origin), ('picked_up', 'Parcel picked up', origin),
        ('origin_hub', 'Arrived at origin hub', origin), ('in_transit', 'In transit', f'{origin} → {destination}'),
        ('destination_hub', 'Arrived at destination hub', destination),
        ('out_for_delivery', 'Out for delivery', destination), ('delivered', 'Delivered', destination),
    ]
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
    return render(request,'services/servicebooked.html')
