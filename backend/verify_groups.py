import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Ticket
from django.db.models import Count

print("=" * 60)
print("VERIFICATION: Listing Group IDs")
print("=" * 60)

# Check for NULL or empty listing_group_id
null_count = Ticket.objects.filter(listing_group_id__isnull=True).count()
empty_count = Ticket.objects.filter(listing_group_id='').count()
total = Ticket.objects.count()

print(f"\nTotal tickets: {total}")
print(f"Tickets with NULL listing_group_id: {null_count}")
print(f"Tickets with empty listing_group_id: {empty_count}")

if null_count == 0 and empty_count == 0:
    print("\nSUCCESS: All tickets have listing_group_id!")
else:
    print(f"\nERROR: {null_count + empty_count} tickets missing listing_group_id")

# Show top groups
print("\n" + "=" * 60)
print("Top 10 groups by ticket count:")
print("=" * 60)

groups = list(Ticket.objects.exclude(listing_group_id__isnull=True).exclude(listing_group_id='').values('listing_group_id').annotate(
    count=Count('id')
).order_by('-count')[:10])

for g in groups:
    print(f"  {g['listing_group_id']}: {g['count']} tickets")

print("\n" + "=" * 60)



