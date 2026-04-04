# Generated manually for 15% fee model (10% buyer + 5% seller).

from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations, models


def backfill_seller_fees_and_net(apps, schema_editor):
    Order = apps.get_model('users', 'Order')
    quant = Decimal('0.01')
    qs = Order.objects.exclude(final_negotiated_price__isnull=True).only(
        'id', 'final_negotiated_price', 'seller_service_fee'
    )
    for o in qs.iterator(chunk_size=500):
        base = o.final_negotiated_price
        if base is None:
            continue
        b = Decimal(str(base))
        sf = (b * Decimal('0.05')).quantize(quant, rounding=ROUND_HALF_UP)
        nsr = (b - sf).quantize(quant, rounding=ROUND_HALF_UP)
        cur_sf = getattr(o, 'seller_service_fee', None)
        if cur_sf is None or Decimal(str(cur_sf or 0)) == 0:
            Order.objects.filter(pk=o.pk).update(
                seller_service_fee=sf,
                net_seller_revenue=nsr,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0040_venue_venue_section_and_ticket_seating'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='seller_service_fee',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='5% seller-side platform fee (withheld from final_negotiated_price)',
                max_digits=10,
            ),
        ),
        migrations.RunPython(backfill_seller_fees_and_net, migrations.RunPython.noop),
    ]
