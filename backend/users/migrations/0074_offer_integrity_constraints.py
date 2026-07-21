from decimal import Decimal

from django.db import migrations, models


def repair_legacy_offer_values(apps, schema_editor):
    Offer = apps.get_model('users', 'Offer')
    Offer.objects.filter(amount__lte=0).update(amount=Decimal('0.01'), status='expired')
    Offer.objects.filter(quantity__lt=1).update(quantity=1, status='expired')
    Offer.objects.filter(offer_round_count__gt=2).update(
        offer_round_count=2,
        status='expired',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0073_alter_globalfeesettings_options'),
    ]

    operations = [
        migrations.RunPython(repair_legacy_offer_values, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='offer',
            constraint=models.CheckConstraint(
                condition=models.Q(amount__gt=Decimal('0.00')),
                name='users_offer_amount_positive',
            ),
        ),
        migrations.AddConstraint(
            model_name='offer',
            constraint=models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name='users_offer_quantity_positive',
            ),
        ),
        migrations.AddConstraint(
            model_name='offer',
            constraint=models.CheckConstraint(
                condition=models.Q(offer_round_count__lte=2),
                name='users_offer_round_max_two',
            ),
        ),
    ]
