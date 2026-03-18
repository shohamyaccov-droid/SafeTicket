"""
Script to fix existing tickets by assigning listing_group_id
Groups tickets by: seller + price + created_at (within 1 minute window)
Run: python manage.py shell < fix_listing_groups.py
Or activate venv and run: python fix_listing_groups.py
"""
import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Ticket
from django.db.models import Count
from django.utils import timezone
import uuid

print("=" * 60)
print("FIXING LISTING GROUP IDs")
print("=" * 60)

# Get all tickets without listing_group_id
tickets_without_group = Ticket.objects.filter(
    listing_group_id__isnull=True
) | Ticket.objects.filter(listing_group_id='')

print(f"\nTickets without listing_group_id: {tickets_without_group.count()}")

# AGGRESSIVE GROUPING: Group ALL tickets with same seller + price + event
# This groups all tickets that should be together, regardless of when they were created
from collections import defaultdict

ticket_groups = defaultdict(list)

for ticket in tickets_without_group:
    # Create a key based on seller, price, and event
    # Use event_id if available, otherwise use event_name as fallback
    event_key = ticket.event_id if ticket.event_id else (ticket.event_name or 'no_event')
    key = (ticket.seller_id, str(ticket.original_price), event_key)
    ticket_groups[key].append(ticket)

print(f"\nFound {len(ticket_groups)} potential groups")

# Assign listing_group_id to each group
fixed_count = 0
for key, tickets in ticket_groups.items():
    # Group ALL tickets that match, even if only 1 ticket (for consistency)
    # Generate a new listing_group_id for this group
    group_id = str(uuid.uuid4())
    
    # Update all tickets in this group
    for ticket in tickets:
        ticket.listing_group_id = group_id
        ticket.save(update_fields=['listing_group_id'])
        fixed_count += 1
    
    if len(tickets) > 1:
        print(f"  Grouped {len(tickets)} tickets: seller={key[0]}, price={key[1]}, event={key[2]}")
    else:
        print(f"  Assigned listing_group_id to 1 ticket: seller={key[0]}, price={key[1]}, event={key[2]}")

print(f"\nFixed {fixed_count} tickets")
remaining = Ticket.objects.filter(listing_group_id__isnull=True).count() + Ticket.objects.filter(listing_group_id='').count()
print(f"  Remaining tickets without group: {remaining}")

# VALIDATION: Ensure no tickets have NULL listing_group_id
if remaining > 0:
    print(f"\n  WARNING: {remaining} tickets still have NULL listing_group_id!")
    print("  Fixing remaining tickets...")
    # Assign individual listing_group_id to any remaining tickets
    for ticket in Ticket.objects.filter(listing_group_id__isnull=True) | Ticket.objects.filter(listing_group_id=''):
        ticket.listing_group_id = str(uuid.uuid4())
        ticket.save(update_fields=['listing_group_id'])
        fixed_count += 1
    print(f"  Fixed {remaining} remaining tickets")
    
final_count = Ticket.objects.filter(listing_group_id__isnull=True).count() + Ticket.objects.filter(listing_group_id='').count()
print(f"\n  Final count of tickets without listing_group_id: {final_count}")
if final_count == 0:
    print("  SUCCESS: All tickets now have listing_group_id!")
else:
    print(f"  ERROR: {final_count} tickets still missing listing_group_id")

# Verify the fix
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

group_counts = list(Ticket.objects.exclude(listing_group_id__isnull=True).exclude(listing_group_id='').values('listing_group_id').annotate(
    count=Count('id')
).order_by('-count')[:10])

print(f"\nTop 10 groups after fix:")
for item in group_counts:
    print(f"  Group '{item['listing_group_id']}': {item['count']} tickets")

print("\n" + "=" * 60)
print("Fix complete!")
print("=" * 60)

