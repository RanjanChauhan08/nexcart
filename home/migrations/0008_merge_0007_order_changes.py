from django.db import migrations


class Migration(migrations.Migration):
    # This migration merges two branches of development that both altered
    # the Order model in migration 0007.
    dependencies = [
        ('home', '0007_alter_order_options'),
        ('home', '0007_order_cancellation'),  # Adds cancellation fields
    ]

    operations = []
