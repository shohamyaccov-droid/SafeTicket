#!/usr/bin/env python
"""
E2E Ping-Pong Negotiation Simulation
=====================================
Simulates a full offer/counter-offer flow between Buyer (User A) and Seller (User B).
Run from project root: python e2e_pingpong_sim.py
"""
import os
import sys
from datetime import timedelta
from decimal import Decimal

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')

import django
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import Offer, Ticket, Event, Artist

User = get_user_model()


def log(msg):
    print(f"  {msg}")


def main():
    print("\n" + "=" * 60)
    print("  E2E PING-PONG NEGOTIATION SIMULATION")
    print("=" * 60)

    # Get or create users
    buyer, _ = User.objects.get_or_create(
        username='e2e_buyer',
        defaults={'email': 'buyer@e2e.test', 'password': 'pbkdf2_sha256$test'}
    )
    buyer.set_password('testpass123')
    buyer.save()

    seller, _ = User.objects.get_or_create(
        username='e2e_seller',
        defaults={'email': 'seller@e2e.test', 'password': 'pbkdf2_sha256$test'}
    )
    seller.set_password('testpass123')
    seller.save()

    log(f"User A (Buyer):  {buyer.username}")
    log(f"User B (Seller): {seller.username}")

    # Get or create event + ticket
    artist, _ = Artist.objects.get_or_create(name='E2E Test Artist', defaults={})
    event, _ = Event.objects.get_or_create(
        name='E2E Test Concert',
        defaults={
            'artist': artist,
            'date': timezone.now() + timedelta(days=30),
            'venue': 'מנורה מבטחים',
            'city': 'תל אביב',
            'status': 'upcoming',
        }
    )
    ticket, _ = Ticket.objects.get_or_create(
        seller=seller,
        event=event,
        defaults={
            'original_price': Decimal('200.00'),
            'asking_price': Decimal('200.00'),
            'status': 'active',
            'verification_status': 'מאומת',
            'available_quantity': 2,
        }
    )
    if ticket.status != 'active':
        ticket.status = 'active'
        ticket.save()

    log(f"Ticket: {event.name} (ILS {ticket.asking_price}) - owned by {seller.username}")
    print()

    expires_at = timezone.now() + timedelta(hours=48)

    # --- ROUND 0: Buyer makes initial offer of 100 ---
    print("-" * 60)
    print("  ROUND 0: Buyer makes initial offer")
    print("-" * 60)
    offer0 = Offer.objects.create(
        buyer=buyer,
        ticket=ticket,
        amount=Decimal('100.00'),
        quantity=1,
        offer_round_count=0,
        status='pending',
        expires_at=expires_at,
    )
    log(f"User A (Buyer) -> Offer #{offer0.id}: ILS 100 on {event.name}")
    log(f"  Status: {offer0.status}, Round: {offer0.offer_round_count}")
    print()

    # --- Seller queries received offers ---
    print("-" * 60)
    print("  SELLER DASHBOARD: Received offers")
    print("-" * 60)
    received = Offer.objects.filter(ticket__seller=seller).exclude(status='expired').order_by('-created_at')
    for o in received:
        log(f"  Offer #{o.id}: ILS {o.amount} from {o.buyer.username} (Round {o.offer_round_count}, {o.status})")
    log("  -> Seller sees the offer. Can: Accept / Reject / Counter")
    print()

    # --- ROUND 1: Seller counters with 150 ---
    print("-" * 60)
    print("  ROUND 1: Seller counters with ILS 150")
    print("-" * 60)
    offer0.status = 'countered'
    offer0.save()
    offer1 = Offer.objects.create(
        buyer=buyer,
        ticket=ticket,
        amount=Decimal('150.00'),
        quantity=1,
        offer_round_count=1,
        parent_offer=offer0,
        status='pending',
        expires_at=timezone.now() + timedelta(hours=24),
    )
    log(f"User B (Seller) -> Counter Offer #{offer1.id}: ILS 150")
    log(f"  Original offer #{offer0.id} marked as 'countered'")
    print()

    # --- Buyer queries received offers (counter from seller) ---
    print("-" * 60)
    print("  BUYER DASHBOARD: Received offers (seller's counter)")
    print("-" * 60)
    # Buyer receives offers on tickets they don't own - but the counter is ON the ticket.
    # Received for buyer = offers where ticket.seller != buyer... no.
    # Actually: "received" = offers where YOU are the recipient. For round 1, buyer is recipient.
    # The API received endpoint filters by ticket__seller=user. So seller sees offers on their tickets.
    # For buyer to see the counter, they'd see it in "sent" - no, the counter has buyer=buyer (same).
    # The counter offer has buyer=buyer (original buyer), so it appears in buyer's "sent"? No - buyer didn't create it.
    # The Offer model: buyer is always the original buyer. So offer1 has buyer=buyer. It's on seller's ticket.
    # So ticket__seller=seller. So offer1 appears in SELLER's received, not buyer's!
    # The recipient of round 1 is the BUYER. So the buyer should see it. But the received endpoint
    # returns ticket__seller=current_user. So only the ticket owner (seller) sees it in received.
    # So there's a design: "received" = offers on my tickets. The counter (round 1) is on seller's ticket.
    # So it appears in seller's received. But the seller created it! So the seller shouldn't act on it.
    # The BUYER needs to see it. The buyer's "received" would need to be different - offers where
    # the current user is the RECIPIENT. So we need offers where (round 0,2 and ticket.seller=user) OR
    # (round 1 and buyer=user). The current API received = ticket__seller=user. So buyer never sees
    # the round 1 counter in "received". They'd see it in "sent" - but sent = buyer=user. So offer1
    # has buyer=buyer, so it WOULD appear in buyer's sent! But the buyer didn't send it - the seller
    # countered. So the offer has buyer=buyer (the original buyer). So it appears in buyer's "sent"
    # list. And for sent, isRecipient = (round 1 && !isSeller) = true when viewing as buyer.
    # So the buyer sees it in "sent" tab (because it has their buyer id), and isRecipient is true.
    # Good.
    sent_by_buyer = Offer.objects.filter(buyer=buyer).exclude(status='expired').order_by('-created_at')
    for o in sent_by_buyer:
        log(f"  Offer #{o.id}: ILS {o.amount} (Round {o.offer_round_count}, {o.status})")
    log("  -> Buyer sees counter in 'Sent' tab (offer has buyer=them). Can: Accept / Reject / Counter")
    print()

    # --- ROUND 2: Buyer counters with 120 ---
    print("-" * 60)
    print("  ROUND 2: Buyer counters with ILS 120 (final)")
    print("-" * 60)
    offer1.status = 'countered'
    offer1.save()
    offer2 = Offer.objects.create(
        buyer=buyer,
        ticket=ticket,
        amount=Decimal('120.00'),
        quantity=1,
        offer_round_count=2,
        parent_offer=offer1,
        status='pending',
        expires_at=timezone.now() + timedelta(hours=24),
    )
    log(f"User A (Buyer) -> Final Counter Offer #{offer2.id}: ILS 120")
    log(f"  (Max rounds reached - no more counters)")
    print()

    # --- Seller queries received offers (final counter) ---
    print("-" * 60)
    print("  SELLER DASHBOARD: Received offers (buyer's final counter)")
    print("-" * 60)
    received2 = Offer.objects.filter(ticket__seller=seller).exclude(status='expired').order_by('-created_at')
    for o in received2:
        if o.status == 'pending':
            log(f"  Offer #{o.id}: ILS {o.amount} from {o.buyer.username} (Round {o.offer_round_count}, {o.status})")
    log("  -> Seller sees final counter. Can: Accept / Reject (no more Counter - round 2)")
    print()

    # --- Seller ACCEPTS the final offer ---
    print("-" * 60)
    print("  SELLER ACCEPTS Offer #{}".format(offer2.id))
    print("-" * 60)
    offer2.status = 'accepted'
    offer2.accepted_at = timezone.now()
    offer2.checkout_expires_at = timezone.now() + timedelta(hours=4)
    offer2.save()
    # Reject other pending on same ticket
    Offer.objects.filter(ticket=ticket, status='pending').exclude(id=offer2.id).update(status='rejected')
    log(f"  Offer #{offer2.id} ACCEPTED at ILS {offer2.amount}")
    log(f"  Checkout window: 4 hours")
    print()

    # --- Summary ---
    print("=" * 60)
    print("  NEGOTIATION COMPLETE")
    print("=" * 60)
    log("  Flow: 100 -> 150 -> 120 -> ACCEPTED")
    log(f"  Final price: ILS {offer2.amount}")
    log(f"  Buyer: {buyer.username}, Seller: {seller.username}")
    print()


if __name__ == '__main__':
    main()
