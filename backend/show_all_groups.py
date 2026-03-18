"""
Show all groups and their counts - Verification script
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

print("=" * 60)
print("ALL GROUPS AND THEIR COUNTS - VERIFICATION")
print("=" * 60)

# Get all groups with their counts
all_groups = list(Ticket.objects.exclude(listing_group_id__isnull=True).exclude(listing_group_id='').values('listing_group_id').annotate(
    count=Count('id')
).order_by('-count'))

print(f"\nTotal groups: {len(all_groups)}")
print("\nAll groups (sorted by ticket count):")

for i, group in enumerate(all_groups, 1):
    group_id = group['listing_group_id']
    count = group['count']
    
    # Get sample ticket to show details
    sample = Ticket.objects.filter(listing_group_id=group_id).first()
    if sample:
        event_id = sample.event_id if sample.event_id else 'None'
        event_name = sample.event.name if sample.event else (sample.event_name or 'Unknown')
        price = str(sample.asking_price)
        statuses = list(Ticket.objects.filter(listing_group_id=group_id).values_list('status', flat=True).distinct())
        active_count = Ticket.objects.filter(listing_group_id=group_id, status='active').count()
        
        print(f"\n{i}. Group ID: {group_id}")
        print(f"   Total tickets: {count}")
        print(f"   Active tickets: {active_count}")
        event_name_safe = event_name.encode('ascii', 'replace').decode('ascii') if event_name else 'Unknown'
        print(f"   Event ID: {event_id}")
        print(f"   Event Name: {event_name_safe}")
        print(f"   Price: {price}")
        print(f"   Statuses: {', '.join(statuses)}")
    else:
        print(f"\n{i}. Group ID: {group_id} - {count} tickets (no sample found)")

# Summary
multi_ticket = [g for g in all_groups if g['count'] > 1]
print(f"\n" + "=" * 60)
print(f"SUMMARY")
print("=" * 60)
print(f"Total groups: {len(all_groups)}")
print(f"Groups with more than 1 ticket: {len(multi_ticket)}")
print(f"Groups with 1 ticket: {len(all_groups) - len(multi_ticket)}")

if len(multi_ticket) > 0:
    print(f"\nGroups that should appear as grouped listings:")
    for g in multi_ticket:
        sample = Ticket.objects.filter(listing_group_id=g['listing_group_id']).first()
        if sample:
            event_info = sample.event.name if sample.event else (sample.event_name or 'Unknown')
            event_info_safe = event_info.encode('ascii', 'replace').decode('ascii') if event_info else 'Unknown'
            price_info = str(sample.asking_price)
            active = Ticket.objects.filter(listing_group_id=g['listing_group_id'], status='active').count()
            print(f"  - {g['count']} tickets ({active} active): Event ID {sample.event_id}, Price {price_info}")
else:
    print("\nWARNING: No groups found with more than 1 ticket!")

print("\n" + "=" * 60)

