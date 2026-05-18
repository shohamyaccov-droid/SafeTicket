# Generated manually for TradeTix wallet rollout.

from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model('users', 'User')
    UserWallet = apps.get_model('wallets', 'UserWallet')
    for user in User.objects.all().iterator(chunk_size=500):
        UserWallet.objects.get_or_create(user_id=user.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0001_wallet_delayed_payout_models'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
