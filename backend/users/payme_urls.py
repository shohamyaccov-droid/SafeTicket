"""URLConf mounted at /api/payments/ — webhook and related PSP routes."""
from django.urls import path

from .payme_views import payme_webhook

urlpatterns = [
    path('webhook/', payme_webhook, name='payme_webhook'),
]
