from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0072_launch_loss_leader_promo'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='globalfeesettings',
            options={
                'verbose_name': 'Platform settings (fees)',
                'verbose_name_plural': 'Platform settings (fees)',
            },
        ),
    ]
