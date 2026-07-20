from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0010_product_category_profile_store_name')]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_postal_code',
            field=models.CharField(blank=True, max_length=6),
        ),
    ]
