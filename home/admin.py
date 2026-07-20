from django.contrib import admin
from home.models import Contact, Product, Profile, ServiceBooking

admin.site.register(Contact)
admin.site.register(ServiceBooking)
admin.site.register(Profile)
admin.site.register(Product)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phnumber')
