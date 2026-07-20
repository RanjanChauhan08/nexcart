import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Creates a superuser from environment variables (ADMIN_USER, ADMIN_EMAIL, ADMIN_PASSWORD)'

    def handle(self, *args, **options):
        username = os.getenv('ADMIN_USER')
        email = os.getenv('ADMIN_EMAIL')
        password = os.getenv('ADMIN_PASSWORD')

        if not all([username, email, password]):
            self.stdout.write(self.style.ERROR('ADMIN_USER, ADMIN_EMAIL, and ADMIN_PASSWORD must be set in the environment.'))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'Superuser "{username}" already exists.'))
        else:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Successfully created superuser "{username}"'))