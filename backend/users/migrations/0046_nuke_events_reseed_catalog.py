# Data migration: pre-launch catalog reset — delete all Event/Ticket rows, then re-seed from seed_production.
#
# PRODUCTION SAFETY: never wipe when production lock is active (RENDER=true or DEBUG=False),
# and never wipe when any Order rows already exist.

from django.db import migrations


def nuke_events_and_tickets_then_reseed(apps, schema_editor):
    """
    Seed creates users. Wallet post_save must not touch DB until wallets.0001 creates tables —
    wallets.signals sets SKIP_WALLET_SIGNAL while seeding.
    """
    try:
        from users.production_safety import is_production_locked

        if is_production_locked():
            # Live / Render / non-debug — historical nuke must never execute.
            return
    except Exception:
        # If safety module cannot load, refuse wipe rather than risk production.
        return

    Order = apps.get_model('users', 'Order')
    if Order.objects.exists():
        # Live / restored DB with marketplace history — do not delete Events/Tickets.
        return

    try:
        import wallets.signals as wallet_sig
    except ImportError:
        wallet_sig = None

    if wallet_sig is not None:
        wallet_sig.SKIP_WALLET_SIGNAL = True

    Ticket = apps.get_model('users', 'Ticket')
    Event = apps.get_model('users', 'Event')
    Ticket.objects.all().delete()
    Event.objects.all().delete()

    try:
        from seed_production import run_after_total_wipe

        run_after_total_wipe(historical_apps=apps)
    finally:
        if wallet_sig is not None:
            wallet_sig.SKIP_WALLET_SIGNAL = False


def noop_reverse(apps, schema_editor):
    """Irreversible: cannot restore wiped marketplace data."""
    pass


class Migration(migrations.Migration):
    """
    Historical pre-launch wipe. Kept for migration graph compatibility.

    On local DEBUG fresh DBs (no orders) it may reseed the catalog once.
    On production / RENDER / any DB with orders: no-op.
    """

    atomic = False  # seed performs HTTP image fetches; avoid holding one DB transaction open

    dependencies = [
        ('users', '0045_ticketalert_phone'),
    ]

    operations = [
        migrations.RunPython(nuke_events_and_tickets_then_reseed, noop_reverse),
    ]
