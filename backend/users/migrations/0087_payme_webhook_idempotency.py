from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0086_seed_meirim_bslichot'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayMeWebhookIdempotency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('idempotency_key', models.CharField(db_index=True, max_length=191, unique=True)),
                ('payme_sale_id', models.CharField(blank=True, default='', max_length=128)),
                ('status', models.CharField(
                    choices=[('processing', 'Processing'), ('completed', 'Completed')],
                    default='processing',
                    max_length=16,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payme_idempotency_rows',
                    to='users.order',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='paymewebhookidempotency',
            index=models.Index(fields=['order', 'status'], name='users_payme_idemp_ord_sts'),
        ),
    ]
