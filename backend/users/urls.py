from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    verify_email,
    CustomTokenObtainPairView,
    CookieTokenRefreshView,
    csrf_token_view,
    logout_view,
    user_profile,
    upgrade_to_seller,
    user_activity,
    order_receipt,
    update_ticket_price,
    create_order,
    guest_checkout,
    confirm_order_payment,
    payment_simulation,
    TicketViewSet,
    EventViewSet,
    ArtistViewSet,
    OfferViewSet,
    ContactMessageViewSet,
    EventRequestViewSet,
    create_ticket_alert,
    admin_pending_tickets,
    admin_approve_ticket,
    admin_reject_ticket,
    admin_dashboard_stats,
    admin_transactions,
    admin_cancel_order,
)

app_name = 'users'

# Router for ViewSet
router = DefaultRouter()
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'events', EventViewSet, basename='event')
router.register(r'artists', ArtistViewSet, basename='artist')
router.register(r'offers', OfferViewSet, basename='offer')
router.register(r'contact-messages', ContactMessageViewSet, basename='contact-message')
router.register(r'event-requests', EventRequestViewSet, basename='event-request')

urlpatterns = [
    path('csrf/', csrf_token_view, name='csrf_token'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', verify_email, name='verify_email'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', user_profile, name='profile'),
    path('me/upgrade-to-seller/', upgrade_to_seller, name='upgrade_to_seller'),
    path('dashboard/', user_activity, name='user_activity'),
    path('orders/<int:order_id>/receipt/', order_receipt, name='order_receipt'),
    path('tickets/<int:ticket_id>/update-price/', update_ticket_price, name='update_ticket_price'),
    path('payments/simulate/', payment_simulation, name='payment_simulation'),
    path('orders/', create_order, name='create_order'),
    path('orders/guest/', guest_checkout, name='guest_checkout'),
    path('orders/<int:order_id>/confirm-payment/', confirm_order_payment, name='confirm_order_payment'),
    path('alerts/', create_ticket_alert, name='create_ticket_alert'),
    path('admin/pending-tickets/', admin_pending_tickets, name='admin_pending_tickets'),
    path('admin/dashboard/stats/', admin_dashboard_stats, name='admin_dashboard_stats'),
    path('admin/transactions/', admin_transactions, name='admin_transactions'),
    path('admin/orders/<int:order_id>/cancel/', admin_cancel_order, name='admin_cancel_order'),
    path('admin/tickets/<int:ticket_id>/approve/', admin_approve_ticket, name='admin_approve_ticket'),
    path('admin/tickets/<int:ticket_id>/reject/', admin_reject_ticket, name='admin_reject_ticket'),
    path('', include(router.urls)),
]

