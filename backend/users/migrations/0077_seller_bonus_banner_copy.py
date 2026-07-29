from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0076_buyer_fee_seven_percent'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerbonuscampaign',
            name='show_on_site',
            field=models.BooleanField(
                default=True,
                help_text='Show the top marketing banner on the site (independent of remaining bonus slots).',
            ),
        ),
        migrations.AddField(
            model_name='sellerbonuscampaign',
            name='banner_text',
            field=models.TextField(
                blank=True,
                default='🎁 20 ₪ בונוס למוכרים!',
                help_text='Marketing banner message. Edit anytime in Admin — no code deploy needed.',
            ),
        ),
        migrations.AddField(
            model_name='sellerbonuscampaign',
            name='banner_coupon_code',
            field=models.CharField(
                blank=True,
                default='SAFE20',
                help_text='Optional coupon code shown in bold after the banner text (leave blank to hide).',
                max_length=40,
            ),
        ),
    ]
