#!/usr/bin/env python
"""
Quick script to check database for listing_group_id consistency
Run: python manage.py shell < check_database.py
Or: python manage.py shell, then paste this code
"""
from users.models import Ticket
from django.db.models import Count, Q

# Check all tickets with their listing_group_id
print("=" * 60)
print("DATABASE AUDIT: Listing Group IDs")
print("=" * 60)

# Get all unique listing_group_ids with their counts
group_counts = Ticket.objects.values('listing_group_id').annotate(
    count=Count('id')
).order_by('-count')

print(f"\nTotal unique listing_group_ids: {group_counts.count()}")
print("\nGroup counts:")
for item in group_counts[:20]:  # Show first 20
    group_id = item['listing_group_id']
    count = item['count']
    if group_id:
        print(f"  '{group_id}' (type: {type(group_id).__name__}): {count} tickets")
    else:
        print(f"  NULL/Empty: {count} tickets")

# Check for tickets with same listing_group_id but different statuses
print("\n" + "=" * 60)
print("Checking for grouped tickets (listing_group_id not null):")
print("=" * 60)

grouped_tickets = Ticket.objects.exclude(listing_group_id__isnull=True).exclude(listing_group_id='')
print(f"Total tickets with listing_group_id: {grouped_tickets.count()}")

# Show sample grouped tickets
sample_groups = grouped_tickets.values('listing_group_id').annotate(
    count=Count('id'),
    active_count=Count('id', filter=Q(status='active'))
).order_by('-count')[:10]

print("\nSample groups (first 10):")
for group in sample_groups:
    group_id = group['listing_group_id']
    total = group['count']
    active = group['active_count']
    print(f"  Group '{group_id}': {total} total tickets, {active} active")

# Check for potential issues (spaces, different formats)
print("\n" + "=" * 60)
print("Checking for data inconsistencies:")
print("=" * 60)

# Check for tickets with spaces in listing_group_id
tickets_with_spaces = grouped_tickets.filter(listing_group_id__contains=' ')
if tickets_with_spaces.exists():
    print(f"WARNING: {tickets_with_spaces.count()} tickets have spaces in listing_group_id")
    for t in tickets_with_spaces[:5]:
        print(f"  Ticket {t.id}: '{t.listing_group_id}'")
else:
    print("✓ No spaces found in listing_group_id")

# Check for tickets with same seller+price but different listing_group_id
print("\nChecking for tickets that should be grouped but aren't:")
from django.db.models import Q
same_seller_price = Ticket.objects.values('seller', 'original_price').annotate(
    count=Count('id'),
    unique_groups=Count('listing_group_id', distinct=True)
).filter(count__gt=1, unique_groups__gt=1)

if same_seller_price.exists():
    print(f"WARNING: {same_seller_price.count()} seller+price combinations have multiple listing_group_ids")
    for item in same_seller_price[:5]:
        print(f"  Seller {item['seller']}, Price {item['original_price']}: {item['count']} tickets, {item['unique_groups']} different groups")
else:
    print("✓ No inconsistencies found")

print("\n" + "=" * 60)
print("Audit complete!")
print("=" * 60)

