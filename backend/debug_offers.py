"""
Debug script to check Offer database state
Run with: python manage.py shell < debug_offers.py
Or: python debug_offers.py (with Django setup)
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Offer, Ticket, User

print("="*80)
print("OFFER DATABASE DEBUG REPORT")
print("="*80)

# Get all offers
all_offers = Offer.objects.select_related('buyer', 'ticket', 'ticket__seller', 'ticket__event').all().order_by('-created_at')

print(f"\nTotal Offers in Database: {all_offers.count()}\n")

if all_offers.count() == 0:
    print("[WARNING] No offers found in database!")
    sys.exit(0)

print("Offer ID | Buyer Username | Ticket ID | Seller Username | Amount | Status | Created At")
print("-" * 100)

for offer in all_offers:
    buyer_username = offer.buyer.username if offer.buyer else 'N/A'
    ticket_id = offer.ticket.id if offer.ticket else 'N/A'
    seller_username = offer.ticket.seller.username if offer.ticket and offer.ticket.seller else 'N/A'
    amount = offer.amount
    status = offer.status
    created_at = offer.created_at.strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"{offer.id:8} | {buyer_username:15} | {ticket_id:9} | {seller_username:15} | {amount:6.2f} | {status:7} | {created_at}")

# Check specific users
print("\n" + "="*80)
print("SPECIFIC USER CHECKS")
print("="*80)

# Check for Ophir
ophir = User.objects.filter(username__iexact='ophir').first()
if ophir:
    print(f"\n[INFO] User 'Ophir' (ID: {ophir.id})")
    ophir_offers_sent = Offer.objects.filter(buyer=ophir).count()
    print(f"   Offers Sent (as buyer): {ophir_offers_sent}")
    
    ophir_tickets = Ticket.objects.filter(seller=ophir)
    print(f"   Tickets Owned: {ophir_tickets.count()}")
    if ophir_tickets.count() > 0:
        ticket_ids = list(ophir_tickets.values_list('id', flat=True))
        print(f"   Ticket IDs: {ticket_ids}")
        
        # Check offers on Ophir's tickets
        offers_on_ophir_tickets = Offer.objects.filter(ticket__seller=ophir)
        print(f"   Offers Received (on Ophir's tickets): {offers_on_ophir_tickets.count()}")
        for offer in offers_on_ophir_tickets:
            print(f"      - Offer {offer.id}: Buyer={offer.buyer.username}, Amount={offer.amount}, Status={offer.status}")
else:
    print("\n[WARNING] User 'Ophir' not found in database")

# Check for Shoham
shoham = User.objects.filter(username__iexact='shoham').first()
if shoham:
    print(f"\n[INFO] User 'Shoham' (ID: {shoham.id})")
    shoham_offers_sent = Offer.objects.filter(buyer=shoham).count()
    print(f"   Offers Sent (as buyer): {shoham_offers_sent}")
    
    shoham_tickets = Ticket.objects.filter(seller=shoham)
    print(f"   Tickets Owned: {shoham_tickets.count()}")
    if shoham_tickets.count() > 0:
        ticket_ids = list(shoham_tickets.values_list('id', flat=True))
        print(f"   Ticket IDs: {ticket_ids}")
        
        # Check offers on Shoham's tickets
        offers_on_shoham_tickets = Offer.objects.filter(ticket__seller=shoham)
        print(f"   Offers Received (on Shoham's tickets): {offers_on_shoham_tickets.count()}")
        for offer in offers_on_shoham_tickets:
            print(f"      - Offer {offer.id}: Buyer={offer.buyer.username}, Amount={offer.amount}, Status={offer.status}")
        
        # Check if Ophir made offers on Shoham's tickets
        if ophir:
            ophir_to_shoham = Offer.objects.filter(buyer=ophir, ticket__seller=shoham)
            print(f"\n   [CHECK] Offers from Ophir to Shoham: {ophir_to_shoham.count()}")
            for offer in ophir_to_shoham:
                print(f"      - Offer {offer.id}: Ticket {offer.ticket.id}, Amount={offer.amount}, Status={offer.status}, Created={offer.created_at}")
    else:
        print("   [WARNING] Shoham has no tickets listed")
else:
    print("\n[WARNING] User 'Shoham' not found in database")

# Check ORM query simulation
print("\n" + "="*80)
print("ORM QUERY VERIFICATION")
print("="*80)

if shoham:
    print(f"\nSimulating OfferViewSet.received() query for Shoham:")
    print(f"Query: Offer.objects.filter(ticket__seller=shoham).exclude(status='expired')")
    
    queryset = Offer.objects.select_related('buyer', 'ticket', 'ticket__seller', 'ticket__event').filter(
        ticket__seller=shoham
    ).exclude(status='expired').order_by('-created_at')
    
    print(f"Result Count: {queryset.count()}")
    for offer in queryset:
        print(f"   - Offer {offer.id}: Buyer={offer.buyer.username}, Ticket={offer.ticket.id}, Amount={offer.amount}")

print("\n" + "="*80)
print("DEBUG COMPLETE")
print("="*80)
