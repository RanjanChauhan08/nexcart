from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0009_profile_email_verified')]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='store_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='product',
            name='category',
            field=models.CharField(
                choices=[('phone', 'Phones'), ('laptop', 'Laptops'), ('earbuds', 'Earbuds'), ('tablet', 'Tablets')],
                default='phone', max_length=20,
            ),
        ),
    ]
