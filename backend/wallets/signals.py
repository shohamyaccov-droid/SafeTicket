from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from wallets.models import UserWallet

# Set True during users.0046 seed (before wallets tables exist); see that migration.
SKIP_WALLET_SIGNAL = False


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_wallet_for_new_user(sender, instance, created, **kwargs):
    if SKIP_WALLET_SIGNAL or not created:
        return
    UserWallet.objects.get_or_create(user=instance)
