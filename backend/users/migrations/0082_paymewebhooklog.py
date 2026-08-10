from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0081_ticketalert_desired_quantity'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayMeWebhookLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('raw_body', models.TextField(help_text='Exact request.body decoded as UTF-8')),
                ('headers', models.JSONField(blank=True, default=dict)),
                (
                    'is_valid',
                    models.BooleanField(
                        default=False,
                        help_text='True when webhook processing completed without a rejection reason',
                    ),
                ),
                ('error_message', models.TextField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='paymewebhooklog',
            index=models.Index(fields=['-created_at', 'is_valid'], name='users_payme_created_3c8a1d_idx'),
        ),
    ]
