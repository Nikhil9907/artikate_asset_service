# Artikate Asset Checkout Service

A Django REST Framework service for enterprise asset checkout management, status lifecycles, concurrency control, automated overdue notifications via Celery, and analytical reporting.

---

## Tech Stack
- **Framework:** Django 5.0, Django REST Framework
- **Task Queue & Broker:** Celery, Redis
- **Testing:** Pytest, Pytest-Django
- **Auth:** DRF Token Authentication

---

## Core Business Rules
- **Rule 1:** Assets must have status `AVAILABLE` to be checked out (returns `409 Conflict` otherwise).
- **Rule 2:** Inactive employees cannot checkout assets (returns `400 Bad Request`).
- **Rule 3:** Maximum limit of 3 concurrently held checkouts per employee (returns `409 Conflict` on 4th attempt).
- **Rule 4:** `due_at` must be strictly in the future and at most 30 days ahead (returns `400 Bad Request`).
- **Rule 5:** Successful checkout updates asset status to `CHECKED_OUT` atomically.
- **Rule 6:** Return operation transitions asset status to `AVAILABLE` (or `MAINTENANCE` if flagged). Duplicate returns yield `409 Conflict`.
- **Rule 7:** Row-level locking via `select_for_update()` inside `transaction.atomic()` prevents concurrent checkout race conditions.
- **Rule 8:** Unknown `asset_tag` or `employee_code` returns `404 Not Found`.

---

## API Endpoints (`/api/v1/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/health/` | Service & database health check | No |
| `POST` | `/api/v1/auth-token/` | Obtain DRF authentication token | No |
| `GET`, `POST` | `/api/v1/assets/` | List (with category, status, search filters) and register assets | Yes |
| `GET` | `/api/v1/assets/<id>/` | Retrieve asset details and checkout history | Yes |
| `POST` | `/api/v1/checkouts/` | Initiate checkout (`asset_tag`, `employee_code`, `due_at`) | Yes |
| `POST` | `/api/v1/checkouts/<id>/return/` | Process asset return (`condition_note`, `needs_maintenance`) | Yes |
| `GET` | `/api/v1/employees/<employee_code>/summary/` | Aggregate metrics (lifetime, held, overdue, mean hold days) | Yes |
| `GET` | `/api/v1/reports/overdue/` | Paginated report of all currently overdue assets | Yes |

---

## Quickstart (Local Development)

### 1. Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt