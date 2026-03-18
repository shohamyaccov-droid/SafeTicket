"""
Total Database Reset for Listing Groups
1. Delete all existing listing_group_id values
2. Re-group ALL tickets by event_id + asking_price (same event, same price = same group)
"""
import os
import sys
import django

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Ticket
from django.db.models import Count
import uuid

print("=" * 60)
print("TOTAL DATABASE RESET FOR LISTING GROUPS")
print("=" * 60)

# Step 1: Delete all existing listing_group_id values
print("\nStep 1: Clearing all existing listing_group_id values...")
tickets_to_clear = Ticket.objects.all()
count_before = tickets_to_clear.count()
tickets_to_clear.update(listing_group_id=None)
print(f"  Cleared listing_group_id for {count_before} tickets")

# Step 2: Group ALL tickets by event_id + asking_price
print("\nStep 2: Grouping tickets by event_id + asking_price...")
from collections import defaultdict

ticket_groups = defaultdict(list)

# Get all active tickets
all_tickets = Ticket.objects.filter(status='active')
print(f"  Processing {all_tickets.count()} active tickets...")

for ticket in all_tickets:
    # Create key: (event_id, asking_price)
    # Use event_id if available, otherwise use event_name as fallback
    event_key = ticket.event_id if ticket.event_id else (ticket.event_name or 'no_event')
    price_key = str(ticket.asking_price)  # Use asking_price, not original_price
    key = (event_key, price_key)
    ticket_groups[key].append(ticket)

print(f"  Found {len(ticket_groups)} unique event+price combinations")

# Step 3: Assign listing_group_id to each group
print("\nStep 3: Assigning listing_group_id to groups...")
fixed_count = 0
group_stats = []

for key, tickets in ticket_groups.items():
    # Generate a new listing_group_id for this group
    group_id = str(uuid.uuid4())
    
    # Update all tickets in this group
    for ticket in tickets:
        ticket.listing_group_id = group_id
        ticket.save(update_fields=['listing_group_id'])
        fixed_count += 1
    
    group_stats.append({
        'event': key[0],
        'price': key[1],
        'count': len(tickets),
        'group_id': group_id
    })
    
    if len(tickets) > 1:
        event_str = str(key[0])
        price_str = str(key[1])
        print(f"  Grouped {len(tickets)} tickets - event_id: {event_str}, price: {price_str}")

print(f"\n  Assigned listing_group_id to {fixed_count} tickets")

# Step 4: Also handle non-active tickets (assign individual IDs)
print("\nStep 4: Handling non-active tickets...")
non_active = Ticket.objects.filter(status__in=['sold', 'reserved']).filter(listing_group_id__isnull=True)
for ticket in non_active:
    ticket.listing_group_id = str(uuid.uuid4())
    ticket.save(update_fields=['listing_group_id'])
    fixed_count += 1
print(f"  Assigned listing_group_id to {non_active.count()} non-active tickets")

# Step 5: Final verification
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

null_count = Ticket.objects.filter(listing_group_id__isnull=True).count()
empty_count = Ticket.objects.filter(listing_group_id='').count()
total = Ticket.objects.count()

print(f"\nTotal tickets: {total}")
print(f"Tickets with NULL listing_group_id: {null_count}")
print(f"Tickets with empty listing_group_id: {empty_count}")

if null_count == 0 and empty_count == 0:
    print("\nSUCCESS: All tickets have listing_group_id!")
else:
    print(f"\nERROR: {null_count + empty_count} tickets still missing listing_group_id")
    # Fix any remaining
    remaining = Ticket.objects.filter(listing_group_id__isnull=True) | Ticket.objects.filter(listing_group_id='')
    for ticket in remaining:
        ticket.listing_group_id = str(uuid.uuid4())
        ticket.save(update_fields=['listing_group_id'])

# Step 6: Show all groups and their counts
print("\n" + "=" * 60)
print("ALL GROUPS AND THEIR COUNTS")
print("=" * 60)

all_groups = list(Ticket.objects.exclude(listing_group_id__isnull=True).exclude(listing_group_id='').values('listing_group_id').annotate(
    count=Count('id'),
    event_id=Count('event_id', distinct=True),
    asking_price=Count('asking_price', distinct=True)
).order_by('-count'))

print(f"\nTotal groups: {len(all_groups)}")
print("\nGroups (sorted by ticket count):")
for i, group in enumerate(all_groups, 1):
    group_id = group['listing_group_id']
    count = group['count']
    
    # Get sample ticket to show event and price
    sample = Ticket.objects.filter(listing_group_id=group_id).first()
    event_info = sample.event.name if sample and sample.event else (sample.event_name if sample else 'Unknown')
    price_info = str(sample.asking_price) if sample else 'Unknown'
    
    print(f"  {i}. Group '{group_id[:8]}...': {count} tickets")
    print(f"     Event: {event_info}, Price: {price_info}")

# Show groups with more than 1 ticket
multi_ticket_groups = [g for g in all_groups if g['count'] > 1]
print(f"\nGroups with more than 1 ticket: {len(multi_ticket_groups)}")
if len(multi_ticket_groups) > 0:
    print("  These should appear as grouped listings in the frontend:")
    for g in multi_ticket_groups:
        sample = Ticket.objects.filter(listing_group_id=g['listing_group_id']).first()
        event_info = sample.event.name if sample and sample.event else (sample.event_name if sample else 'Unknown')
        price_info = str(sample.asking_price) if sample else 'Unknown'
        sample = Ticket.objects.filter(listing_group_id=g['listing_group_id']).first()
        event_id = sample.event_id if sample else 'N/A'
        print(f"    - {g['count']} tickets: Event ID {event_id}, Price {price_info}")
else:
    print("  WARNING: No groups found with more than 1 ticket!")

print("\n" + "=" * 60)
print("Reset and regrouping complete!")
print("=" * 60)

