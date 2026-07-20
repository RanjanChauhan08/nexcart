import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import home.models


STATUS_CHOICES = [
    ('placed', 'Order placed'), ('confirmed', 'Confirmed'), ('packed', 'Packed'),
    ('picked_up', 'Picked up'), ('origin_hub', 'At origin hub'), ('in_transit', 'In transit'),
    ('destination_hub', 'At destination hub'), ('out_for_delivery', 'Out for delivery'),
    ('delivered', 'Delivered'),
]


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('home', '0005_product_image'),
    ]

    operations = [
        migrations.AddField(model_name='profile', name='city', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='order', name='seller', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='seller_orders', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='order', name='customer_name', field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name='order', name='customer_phone', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='order', name='delivery_address', field=models.TextField(blank=True)),
        migrations.AddField(model_name='order', name='delivery_city', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='order', name='tracking_code', field=models.CharField(default=home.models.generate_tracking_code, editable=False, max_length=12, unique=True)),
        migrations.AddField(model_name='order', name='status', field=models.CharField(choices=STATUS_CHOICES, default='placed', max_length=20)),
        migrations.AddField(model_name='order', name='current_location', field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name='order', name='estimated_delivery', field=models.DateField(blank=True, null=True)),
        migrations.AlterField(model_name='order', name='user', field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to=settings.AUTH_USER_MODEL)),
        migrations.CreateModel(name='OrderItem', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('product_name', models.CharField(max_length=150)), ('price', models.DecimalField(decimal_places=2, max_digits=10)), ('quantity', models.PositiveIntegerField(default=1)),
            ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='home.order')),
            ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='home.product')),
        ]),
        migrations.CreateModel(name='TrackingUpdate', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('status', models.CharField(choices=STATUS_CHOICES, max_length=20)), ('location', models.CharField(max_length=150)), ('note', models.CharField(blank=True, max_length=255)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tracking_updates', to='home.order')),
        ], options={'ordering': ['created_at']}),
    ]
