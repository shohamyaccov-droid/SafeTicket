from django.core.management.base import BaseCommand, CommandError

from users.utils.emails import send_test_welcome_email


class Command(BaseCommand):
    help = 'Send a branded TradeTix HTML test email to verify SMTP configuration.'

    def add_arguments(self, parser):
        parser.add_argument('email_address', help='Recipient email address for the test message.')

    def handle(self, *args, **options):
        email_address = (options.get('email_address') or '').strip()
        if not email_address or '@' not in email_address:
            raise CommandError('Please provide a valid email address.')

        self.stdout.write(f'Sending TradeTix test email to {email_address}...')
        try:
            sent = send_test_welcome_email(email_address)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Failed to send test email: {exc.__class__.__name__}: {exc}'))
            raise CommandError('SMTP test failed. Check EMAIL_* settings and provider logs.') from exc

        if sent:
            self.stdout.write(self.style.SUCCESS(f'Successfully sent TradeTix test email to {email_address}.'))
        else:
            raise CommandError('Email backend reported 0 sent messages.')
