"""
Activate all tickets owned by Shoham
Run with: python manage.py shell < activate_shoham_tickets.py
Or: python activate_shoham_tickets.py (with Django setup)
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Ticket, User

print("="*80)
print("ACTIVATING SHOHAM'S TICKETS")
print("="*80)

# Find Shoham user (case-insensitive)
shoham = User.objects.filter(username__iexact='shoham').first()

if not shoham:
    print("\n[ERROR] User 'shoham' not found in database!")
    print("Available users:", list(User.objects.values_list('username', flat=True)))
    sys.exit(1)

print(f"\n[INFO] Found user: {shoham.username} (ID: {shoham.id})")

# Get all tickets owned by Shoham
shoham_tickets = Ticket.objects.filter(seller=shoham)
print(f"\n[INFO] Found {shoham_tickets.count()} tickets owned by Shoham")

if shoham_tickets.count() == 0:
    print("[WARNING] Shoham has no tickets!")
    sys.exit(0)

# Show current status
print("\nCurrent ticket statuses:")
for ticket in shoham_tickets:
    print(f"  Ticket {ticket.id}: status='{ticket.status}'")

# Activate all tickets
updated = shoham_tickets.update(status='active')
print(f"\n[SUCCESS] Activated {updated} tickets to status='active'")

# Verify
print("\nUpdated ticket statuses:")
for ticket in Ticket.objects.filter(seller=shoham):
    print(f"  Ticket {ticket.id}: status='{ticket.status}'")

print("\n" + "="*80)
print("ACTIVATION COMPLETE")
print("="*80)
