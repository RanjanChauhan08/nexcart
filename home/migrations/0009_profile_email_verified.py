from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0008_merge_0007_order_changes')]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
    ]
