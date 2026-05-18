from django.contrib import admin

from wallets.models import UserWallet, WalletTransaction


@admin.register(UserWallet)
class UserWalletAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'available_balance',
        'locked_balance',
        'created_at',
        'updated_at',
    )
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user',)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'sender_wallet',
        'receiver_wallet',
        'amount',
        'status',
        'associated_event',
        'payme_batch_id',
        'payme_transfer_id',
        'created_at',
        'updated_at',
    )
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = (
        'payme_batch_id',
        'payme_transfer_id',
        'sender_wallet__user__username',
        'receiver_wallet__user__username',
    )
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('sender_wallet', 'receiver_wallet', 'associated_event')
