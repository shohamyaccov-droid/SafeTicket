from django.db import migrations, models
from decimal import Decimal


def recompute_seller_payout_amounts(apps, schema_editor):
    SellerPayout = apps.get_model('users', 'SellerPayout')
    WalletTransaction = apps.get_model('wallets', 'WalletTransaction')
    UserWallet = apps.get_model('wallets', 'UserWallet')
    for payout in SellerPayout.objects.select_related('order').all().iterator():
        order = payout.order
        if order is None:
            continue
        total_paid = order.total_paid_by_buyer or order.total_amount or payout.total_paid
        seller_net = order.net_seller_revenue or order.final_negotiated_price
        if seller_net is None:
            continue
        platform_fee = (order.buyer_service_fee or Decimal('0.00')) + (
            order.seller_service_fee or Decimal('0.00')
        )
        if platform_fee == Decimal('0.00') and total_paid is not None:
            platform_fee = Decimal(total_paid) - Decimal(seller_net)
        old_net = Decimal(payout.net_payout or 0).quantize(Decimal('0.01'))
        new_net = Decimal(seller_net).quantize(Decimal('0.01'))
        SellerPayout.objects.filter(pk=payout.pk).update(
            total_paid=Decimal(total_paid).quantize(Decimal('0.01')),
            platform_fee=Decimal(platform_fee).quantize(Decimal('0.01')),
            net_payout=new_net,
        )
        delta = new_net - old_net
        if delta == Decimal('0.00'):
            continue
        tx = WalletTransaction.objects.filter(
            seller_payout_id=payout.pk,
            transaction_type='SALE_CREDIT',
        ).first()
        if tx is None or tx.receiver_wallet_id is None:
            continue
        update = {'amount': new_net}
        WalletTransaction.objects.filter(pk=tx.pk).update(**update)
        if tx.status == 'COMPLETED':
            UserWallet.objects.filter(pk=tx.receiver_wallet_id).update(
                available_balance=models.F('available_balance') + delta
            )
        else:
            UserWallet.objects.filter(pk=tx.receiver_wallet_id).update(
                locked_balance=models.F('locked_balance') + delta
            )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0059_escrow_release_36_hour_help_text'),
        ('wallets', '0003_wallet_transaction_payout_metadata'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sellerpayout',
            name='net_payout',
            field=models.DecimalField(
                decimal_places=2,
                help_text='Amount owed to the seller after seller-side fees',
                max_digits=10,
            ),
        ),
        migrations.AlterField(
            model_name='sellerpayout',
            name='platform_fee',
            field=models.DecimalField(
                decimal_places=2,
                help_text='TradeTix platform fee (buyer Security Fee plus any seller-side fee)',
                max_digits=10,
            ),
        ),
        migrations.RunPython(recompute_seller_payout_amounts, migrations.RunPython.noop),
    ]
