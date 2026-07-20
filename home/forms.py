from django import forms
from .models import Contact, Product, ServiceBooking


class ServiceBookingForm(forms.ModelForm):
    class Meta:
        model = ServiceBooking
        fields = ['customer_name', 'customer_email', 'customer_phone', 'customer_location', 'device_model', 'problems']


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'phnumber', 'reason_for_contacting']


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'price', 'stock', 'image', 'image_url']