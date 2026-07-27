# TradeTix Locust load test (local / staging only)

## Safety

- **Never** run against production (`tradetix.co.il`, `safeticket-api.onrender.com`). The Locust file aborts if the host looks like production.
- Requires **`DEBUG=True`** so `/api/payments/mock-success/` can finalize without PayMe.
- Creates real DB rows (orders, sold tickets). Use a disposable local DB or reset afterward.

## Setup

```powershell
cd C:\Users\user\Desktop\SafeTicket\backend
# Ensure Postgres/SQLite is up and migrations applied
python manage.py migrate
python manage.py seed_checkout_test_tickets   # or your usual seed

# Terminal A — API with DEBUG
$env:DEBUG="True"
python manage.py runserver 0.0.0.0:8000
```

```powershell
cd C:\Users\user\Desktop\SafeTicket\scripts\loadtest
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

Web UI (recommended first):

```powershell
locust -f locustfile.py --host http://127.0.0.1:8000
```

Open http://localhost:8089 — start with **20 users**, spawn rate **5**, then scale toward 100–500.

Headless:

```powershell
# Light
locust -f locustfile.py --host http://127.0.0.1:8000 --users 50 --spawn-rate 5 --run-time 2m --headless

# Heavier (need enough active tickets or you will mostly see expected 400 "held")
locust -f locustfile.py --host http://127.0.0.1:8000 --users 200 --spawn-rate 20 --run-time 3m --headless
```

Optional:

```powershell
$env:LOCUST_BUY_RATIO="0.15"   # fewer full checkouts
$env:LOCUST_EVENT_ID="42"      # pin one event
```

## What success looks like

| Signal | Healthy | Unhealthy |
|--------|---------|-----------|
| `GET /api/health/` p95 | &lt; 100ms local | timeouts / 5xx |
| Reserve 400 "held" | common under contention | — |
| Guest checkout / mock-success 5xx | rare | investigate DB locks / worker saturation |
| Failure rate excluding expected 400s | &lt; 1% | rising with users |

## Interpreting 100–500 users

`runserver` is single-threaded for most work — it is **not** a capacity proof for Render. For realism locally use:

```powershell
pip install gunicorn
gunicorn safeticket.wsgi:application -b 0.0.0.0:8000 -w 4 --threads 2
```

(from `backend/`, with the same env as runserver).

## Cleanup

```powershell
cd C:\Users\user\Desktop\SafeTicket\backend
python manage.py reset_test_data --execute   # if you use that command in this repo
# or wipe loadtest guest orders manually
```
