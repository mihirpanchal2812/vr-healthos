from django.core.management.base import BaseCommand
from core.models import User

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('password')

    def handle(self, *args, **options):
        u = User.objects.create_superuser(
            username=options['email'],
            email=options['email'],
            password=options['password'],
            role='admin',
        )
        self.stdout.write(f'Admin created: {u.email}')

# Usage:
# python manage.py create_admin admin@example.com yourpassword
