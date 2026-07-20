from django.test import TestCase
from django.urls import reverse
from django.contrib.messages import get_messages

from .models import ServiceBooking


class ServiceBookingTests(TestCase):

    def test_laptop_service_booking_submission(self):
        """
        Tests that a valid service booking for a laptop is created successfully.
        """
        form_data = {
            'customer_name': 'Test Customer',
            'device_model': 'MacBook Pro 2022',
            'customer_location': '123 Test St, Test City',
            'customer_phone': '1234567890',
            'customer_email': 'test@example.com',
            'problems': 'Spilled coffee on keyboard',
        }
        response = self.client.post(reverse('laptopservices'), form_data)

        # Check that we are redirected to the success page
        self.assertRedirects(response, reverse('servicebooked'))

        # Check that a ServiceBooking object was created
        self.assertEqual(ServiceBooking.objects.count(), 1)
        booking = ServiceBooking.objects.first()
        self.assertEqual(booking.device_type, 'laptop')
        self.assertEqual(booking.device_model, 'MacBook Pro 2022')
        self.assertEqual(booking.customer_name, 'Test Customer')
        self.assertEqual(booking.customer_email, 'test@example.com')

        # Check that a success message was sent
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Service booked successfully!')