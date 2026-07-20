from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from home.models import Order, Product


class AuthenticationTests(TestCase):
    @patch('home.views._send_email_code', return_value=True)
    def test_signup_requires_verification_before_creating_account(self, send_code):
        response = self.client.post(reverse('signup'), {
            'email': 'buyer@example.com',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
            'role': 'buyer',
        })

        self.assertRedirects(response, reverse('verify_email'))
        self.assertFalse(User.objects.filter(email='buyer@example.com').exists())
        send_code.assert_called_once()

    def test_password_login_works_for_verified_account(self):
        user = User.objects.create_user(username='buyer', email='buyer@example.com', password='StrongPassword123!')
        user.profile.email_verified = True
        user.profile.save(update_fields=['email_verified'])

        response = self.client.post(reverse('login'), {
            'email': user.email,
            'password': 'StrongPassword123!',
            'action': 'password',
        })

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)


class CartAndOrderTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(username='buyer', email='buyer@example.com', password='StrongPassword123!')
        self.seller = User.objects.create_user(username='seller', email='seller@example.com', password='StrongPassword123!')
        self.seller.profile.role = 'seller'
        self.seller.profile.store_name = 'NexCart Test Store'
        self.seller.profile.save(update_fields=['role', 'store_name'])
        self.product = Product.objects.create(
            seller=self.seller,
            category='phone',
            name='Test Phone',
            price=Decimal('999.00'),
            stock=2,
        )
        self.client.force_login(self.buyer)

    def _set_cart(self, item):
        session = self.client.session
        session['cart'] = [item]
        session.save()

    def test_cart_rejects_items_without_a_real_product(self):
        response = self.client.post(reverse('add_to_cart'), {'name': 'Forged item', 'price': '1'})

        self.assertRedirects(response, reverse('buynow'))
        self.assertEqual(self.client.session.get('cart'), None)

    @patch('home.views._lookup_indian_pin_code', return_value={
        'delivery_city': 'New Delhi, Delhi', 'locality': 'New Delhi GPO', 'state': 'Delhi',
    })
    def test_order_uses_database_price_and_decrements_stock(self, _lookup):
        self._set_cart({
            'product_id': self.product.id,
            'seller_id': self.seller.id,
            'name': 'Forged name',
            'price': '1.00',
            'image': '',
        })

        response = self.client.post(reverse('place_order'), {
            'name': 'Test Buyer',
            'phone': '9876543210',
            'address': '12 Example Street',
            'postal_code': '110001',
        })

        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.total_amount, Decimal('999.00'))
        self.assertEqual(order.items.get().product_name, self.product.name)
        self.assertEqual(order.delivery_postal_code, '110001')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    @patch('home.views._lookup_indian_pin_code', return_value={
        'delivery_city': 'New Delhi, Delhi', 'locality': 'New Delhi GPO', 'state': 'Delhi',
    })
    def test_order_rejects_out_of_stock_cart_item(self, _lookup):
        self.product.stock = 0
        self.product.save(update_fields=['stock'])
        self._set_cart({'product_id': self.product.id, 'seller_id': self.seller.id, 'price': '999.00'})

        response = self.client.post(reverse('place_order'), {
            'name': 'Test Buyer',
            'phone': '9876543210',
            'address': '12 Example Street',
            'postal_code': '110001',
        })

        self.assertRedirects(response, reverse('checkout'))
        self.assertFalse(Order.objects.exists())
