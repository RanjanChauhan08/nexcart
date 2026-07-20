# Generated manually for device image uploads.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0004_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='product_images/'),
        ),
    ]
