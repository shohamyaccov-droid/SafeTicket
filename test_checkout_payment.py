"""
E2E Test: Payment Tolerance - 942 ILS accepted for 855 base (expected 940.50)
Proves backend accepts amount within 2.00 ILS tolerance for JS float vs Python Decimal rounding.

Flow:
1. Create Offer for 855 ILS
2. Accept the offer
3. Simulate frontend sending 942.00 (previously crashed - 1.50 ILS over expected 940.50)
4. Assert backend accepts payment successfully

Run: python test_checkout_payment.py
Requires: server running (python manage.py runserver) from backend/
"""
import requests
import time

API_BASE = 'http://127.0.0.1:8000/api/users'

def get_event_id():
    r = requests.get(f"{API_BASE}/events/", timeout=5)
    if r.status_code == 200:
        data = r.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        if isinstance(results, list) and results:
            return results[0]['id']
        if isinstance(results, dict) and 'id' in results:
            return results['id']
    return 1  # fallback

def get_active_ticket(seller_token):
    """Get first active ticket from any event"""
    r = requests.get(f"{API_BASE}/events/", timeout=5)
    if r.status_code != 200:
        return None
    data = r.json()
    events = data.get('results', data) if isinstance(data, dict) else data
    if not isinstance(events, list) or not events:
        return None
    for ev in events[:5]:
        eid = ev.get('id')
        r2 = requests.get(f"{API_BASE}/events/{eid}/tickets/", timeout=5)
        if r2.status_code == 200:
            tdata = r2.json()
            tickets = tdata.get('results', tdata) if isinstance(tdata, dict) else tdata
            if isinstance(tickets, list):
                for t in tickets:
                    if t.get('status') == 'active':
                        return t
    return None

def create_dummy_pdf():
    return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>startxref
178
%%EOF"""

def main():
    print("=" * 70)
    print("E2E Test: Payment Tolerance - 942 accepted for 855 base (expected 940.50)")
    print("=" * 70)

    # Create users if needed and get tokens
    for user_data in [
        {'username': 'test_seller_offer', 'email': 'seller_tol@test.com', 'password': 'testpass123'},
        {'username': 'test_buyer_offer', 'email': 'buyer_tol@test.com', 'password': 'testpass123'}
    ]:
        requests.post(f"{API_BASE}/register/", json={
            'username': user_data['username'], 'email': user_data['email'],
            'password': user_data['password'], 'password2': user_data['password'],
            'first_name': '', 'last_name': '', 'role': 'buyer'
        }, timeout=5)  # Ignore if exists

    seller_token = None
    buyer_token = None
    for _ in range(3):
        r = requests.post(f"{API_BASE}/login/", json={'username': 'test_seller_offer', 'password': 'testpass123'}, timeout=5)
        if r.status_code == 200:
            seller_token = r.json().get('access')
            break
        time.sleep(1)
    for _ in range(3):
        r = requests.post(f"{API_BASE}/login/", json={'username': 'test_buyer_offer', 'password': 'testpass123'}, timeout=5)
        if r.status_code == 200:
            buyer_token = r.json().get('access')
            break
        time.sleep(1)

    if not seller_token or not buyer_token:
        print("[FAIL] Could not get tokens. Ensure server is running and user test_seller_offer/test_buyer_offer exist.")
        print("       Run: cd backend && python manage.py runserver")
        print("       Then run: cd backend && python test_checkout_payment.py --tolerance")
        return 1

    print("\n1. Finding active ticket...")
    ticket = get_active_ticket(seller_token)
    if not ticket:
        print("[FAIL] No active ticket found. Upload a ticket and ensure it is approved (status=active).")
        return 1
    print(f"   [OK] Ticket ID: {ticket['id']} (event: {ticket.get('event_name', 'N/A')})")

    print("\n2. Creating offer: 855 ILS...")
    r = requests.post(f"{API_BASE}/offers/", json={'ticket': ticket['id'], 'amount': '855', 'quantity': 1},
                     headers={'Authorization': f'Bearer {buyer_token}'})
    if r.status_code != 201:
        print(f"[FAIL] Create offer: {r.status_code} - {r.text[:200]}")
        return 1
    offer = r.json()
    print(f"   [OK] Offer ID: {offer['id']}, Amount: {offer['amount']}")

    print("\n3. Accepting offer...")
    r = requests.post(f"{API_BASE}/offers/{offer['id']}/accept/", headers={'Authorization': f'Bearer {seller_token}'})
    if r.status_code != 200:
        print(f"[FAIL] Accept offer: {r.status_code} - {r.text[:200]}")
        return 1
    print("   [OK] Offer accepted")

    expected = 855 + (855 * 0.10)  # 940.50
    print(f"\n4. Expected total (base * 1.10): {expected:.2f} ILS")
    print("   Frontend sends (rounded): 942.00 ILS (1.50 ILS over)")
    print("   Tolerance: 2.00 ILS -> 942 should be ACCEPTED")

    print("\n5. Simulating payment with amount=942.00 and offer_id...")
    r = requests.post(f"{API_BASE}/payments/simulate/", json={
        'ticket_id': ticket['id'], 'amount': 942.00, 'quantity': 1,
        'timestamp': int(time.time() * 1000), 'offer_id': offer['id']
    }, headers={'Authorization': f'Bearer {buyer_token}'})

    if r.status_code == 200 and r.json().get('success'):
        print("   [OK] Payment ACCEPTED! (942 within 2.00 ILS of 940.50)")
    else:
        print(f"   [FAIL] Payment REJECTED: {r.status_code} - {r.text[:300]}")
        return 1

    print("\n" + "=" * 70)
    print("[PASS] TOLERANCE TEST: Backend accepts 942 for 940.50 expected")
    print("=" * 70)
    return 0

if __name__ == '__main__':
    exit(main())
