from django.db import migrations, models


STATUS_CHOICES = [
    ('placed', 'Order placed'), ('confirmed', 'Confirmed'), ('packed', 'Packed'),
    ('picked_up', 'Picked up'), ('origin_hub', 'At origin hub'), ('in_transit', 'In transit'),
    ('destination_hub', 'At destination hub'), ('out_for_delivery', 'Out for delivery'),
    ('delivered', 'Delivered'), ('cancelled', 'Cancelled by seller'),
]


class Migration(migrations.Migration):
    dependencies = [('home', '0006_order_tracking')]

    operations = [
        migrations.AddField(model_name='order', name='cancellation_reason', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='order', name='cancelled_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(model_name='order', name='status', field=models.CharField(choices=STATUS_CHOICES, default='placed', max_length=20)),
        migrations.AlterField(model_name='trackingupdate', name='status', field=models.CharField(choices=STATUS_CHOICES, max_length=20)),
    ]
