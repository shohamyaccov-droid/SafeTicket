"""URLConf mounted at /api/payments/ — webhook and related PSP routes."""
from django.urls import path

from .grow_views import grow_payment_webhook
from .payme_views import payme_webhook

urlpatterns = [
    path('webhook/', grow_payment_webhook, name='grow_payment_webhook'),
    path('webhook/payme/', payme_webhook, name='payme_webhook'),
]
