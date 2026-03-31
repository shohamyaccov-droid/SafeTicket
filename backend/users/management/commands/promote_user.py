"""
Management command to promote a user to superuser and staff status.

Usage: python manage.py promote_user shoham
"""
from django.core.management.base import BaseCommand
from users.models import User


class Command(BaseCommand):
    help = 'Promote a user to superuser and staff status'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username of the user to promote',
        )

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
            
            # Check current status
            was_superuser = user.is_superuser
            was_staff = user.is_staff
            
            # Promote user
            user.is_superuser = True
            user.is_staff = True
            user.save()
            
            self.stdout.write(self.style.SUCCESS(f'\n=== User Promotion Report ==='))
            self.stdout.write(f'User: {user.username} (ID: {user.id})')
            self.stdout.write(f'Email: {user.email or "N/A"}')
            self.stdout.write(f'\nPrevious Status:')
            self.stdout.write(f'  - is_superuser: {was_superuser}')
            self.stdout.write(f'  - is_staff: {was_staff}')
            self.stdout.write(f'\nNew Status:')
            self.stdout.write(f'  - is_superuser: {user.is_superuser}')
            self.stdout.write(f'  - is_staff: {user.is_staff}')
            self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] User "{username}" has been promoted to superuser and staff!'))
            self.stdout.write(self.style.SUCCESS(
                'The user can access /admin-panel (TradeTix admin dashboard) and /admin/verification.'
            ))
            
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n[ERROR] User with username "{username}" does not exist.'))
            self.stdout.write(self.style.WARNING('Available users:'))
            for u in User.objects.all()[:10]:
                self.stdout.write(f'  - {u.username} (ID: {u.id}, Email: {u.email or "N/A"})')
            if User.objects.count() > 10:
                self.stdout.write(f'  ... and {User.objects.count() - 10} more users')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n[ERROR] An error occurred: {str(e)}'))
