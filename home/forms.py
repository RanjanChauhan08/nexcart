from django import forms
from .models import Contact, ServiceBooking


class ServiceBookingForm(forms.ModelForm):
    class Meta:
        model = ServiceBooking
        fields = ['device_model', 'customer_location', 'customer_phone', 'customer_email', 'problems']


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'phnumber', 'reason_for_contacting']