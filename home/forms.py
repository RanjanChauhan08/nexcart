# --- Core Imports ---
from django import forms

# --- Local Imports ---
from .models import Contact, Product, ServiceBooking


# A form for booking a repair service.
class ServiceBookingForm(forms.ModelForm):
    class Meta:
        model = ServiceBooking
        # Specifies which fields from the ServiceBooking model should be included in the form.
        fields = ['customer_name', 'customer_email', 'customer_phone', 'customer_location', 'device_model', 'problems']


# A form for the "Contact Us" page.
class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'phnumber', 'reason_for_contacting']


# A form for sellers to add or edit a product.
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # We are removing the 'image' field because file uploads are blocked on free
        # PythonAnywhere accounts. Sellers should use the 'image_url' field instead.
        fields = ['name', 'description', 'category', 'price', 'stock', 'image_url']