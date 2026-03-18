import os
import django
import math

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Ticket
from users.views import create_order
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model


def print_result(description, passed, error=None):
    status = "PASS" if passed else "FAIL"
    print(f"{status} - {description}")
    if error:
        print(f"    Details: {error}")


def run_tests():
    User = get_user_model()
    buyer, _ = User.objects.get_or_create(username="qa_split_buyer", defaults={"role": "buyer"})
    seller, _ = User.objects.get_or_create(username="qa_split_seller", defaults={"role": "seller"})

    # Clean up any existing QA tickets
    Ticket.objects.filter(event_name__startswith="[QA Split Test]").delete()

    # Create mock listings (no real event linkage needed for split logic)
    listing_a = Ticket.objects.create(
        seller=seller,
        event_name="[QA Split Test] Listing A",
        original_price=100,
        asking_price=100,
        available_quantity=4,
        split_type='מכור הכל יחד',  # all
        status='active',
    )

    listing_b = Ticket.objects.create(
        seller=seller,
        event_name="[QA Split Test] Listing B",
        original_price=100,
        asking_price=100,
        available_quantity=4,
        split_type='זוגות בלבד',  # pairs
        status='active',
    )

    listing_c = Ticket.objects.create(
        seller=seller,
        event_name="[QA Split Test] Listing C",
        original_price=100,
        asking_price=100,
        available_quantity=4,
        split_type='כל כמות',  # any
        status='active',
    )

    factory = APIRequestFactory()

    def try_purchase(ticket, quantity, description, should_pass):
        data = {
            "ticket": ticket.id,
            "total_amount": math.ceil(float(ticket.original_price) * 1.10) * quantity,
            "quantity": quantity,
            "event_name": ticket.event_name,
        }
        request = factory.post("/api/users/orders/", data, format="json")
        force_authenticate(request, user=buyer)
        response = create_order(request)
        passed = (200 <= response.status_code < 300) if should_pass else (response.status_code == 400)
        error = None
        if not passed:
            error = f"status={response.status_code}, data={getattr(response, 'data', None)}"
        print_result(description, passed, error)

    print("=== QA Split Logic Tests ===")

    # Listing A: 4 tickets, split_type='all'
    try_purchase(listing_a, 1, "Listing A: buying 1 ticket (should FAIL - all)", should_pass=False)
    try_purchase(listing_a, 4, "Listing A: buying 4 tickets (should PASS - all)", should_pass=True)

    # Listing B: 4 tickets, split_type='pairs'
    try_purchase(listing_b, 3, "Listing B: buying 3 tickets (should FAIL - pairs)", should_pass=False)
    try_purchase(listing_b, 2, "Listing B: buying 2 tickets (should PASS - pairs)", should_pass=True)

    # Listing C: 4 tickets, split_type='any'
    try_purchase(listing_c, 3, "Listing C: buying 3 tickets (should PASS - any)", should_pass=True)


if __name__ == "__main__":
    run_tests()

