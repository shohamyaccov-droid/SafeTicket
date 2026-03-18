import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Ticket
from django.db.models import Count, Q

print("=" * 60)
print("DATABASE AUDIT: Listing Group IDs")
print("=" * 60)

# Get all unique listing_group_ids with their counts
group_counts = list(Ticket.objects.values('listing_group_id').annotate(
    count=Count('id')
).order_by('-count'))

print(f"\nTotal unique listing_group_ids: {len(group_counts)}")
print("\nGroup counts (first 20):")
for item in group_counts[:20]:
    group_id = item['listing_group_id']
    count = item['count']
    if group_id:
        print(f"  '{group_id}': {count} tickets")
    else:
        print(f"  NULL/Empty: {count} tickets")

# Check for grouped tickets
print("\n" + "=" * 60)
print("Checking for grouped tickets (listing_group_id not null):")
print("=" * 60)

grouped_tickets = Ticket.objects.exclude(listing_group_id__isnull=True).exclude(listing_group_id='')
print(f"Total tickets with listing_group_id: {grouped_tickets.count()}")

# Show sample grouped tickets with active status
sample_groups = list(grouped_tickets.values('listing_group_id').annotate(
    count=Count('id'),
    active_count=Count('id', filter=Q(status='active'))
).order_by('-count')[:10])

print("\nSample groups (first 10):")
for group in sample_groups:
    group_id = group['listing_group_id']
    total = group['count']
    active = group['active_count']
    print(f"  Group '{group_id}': {total} total tickets, {active} active")

print("\n" + "=" * 60)
print("Audit complete!")
print("=" * 60)



