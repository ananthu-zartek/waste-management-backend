# Dry waste and scrap booking flow

All endpoints require authentication. Customers use their own profile and address;
the server supplies customer, source, driver, status, and payout.

## Safe creation retries

Every `POST /api/v1/bookings/` must include an `Idempotency-Key` header, for
example a newly generated UUID. Reuse that key and the same JSON payload when
retrying a request. Keys are scoped to the customer and limited to 128 characters.
The original HTTP 201 response is stored atomically with the booking and items,
and replayed on retries without reserving additional capacity. A different
payload with the same key returns HTTP 409 under `error`. Failed transactions
do not retain the key. Use a new key for a genuinely new booking.

The replay is the original response, even after the booking is confirmed or
expired. Use GET to fetch its current status. The request is linked to the booking
and is deleted with it through Django's cascading deletion. Deleting a booking
therefore allows its key to be used again; retries after deletion can create a
new booking. Cancellation and expiration retain the booking and its key.

The booking link is temporarily nullable while creation is in progress; it is
saved with the response in the same transaction. When migrating existing request
records, backfill this link from the stored response's booking `id`, checking
customer ownership. Requests for bookings already deleted need separate cleanup;
adding the relationship alone does not repair old records.

## Confirm a customer booking

New customer bookings start as `pending`, with `confirmed_at` unset. They reserve
driver capacity while awaiting confirmation. Admin bookings retain their existing
creation behavior.

Send `POST /api/v1/bookings/{id}/confirm/` with an empty body, authenticated as
the owning customer. Only pending customer bookings can be confirmed, strictly
before `created_at + 30 minutes`. Success returns the updated booking with
`status: confirmed` and `confirmed_at`. At or after the deadline, the API returns
HTTP 400 with `{"error": "Booking confirmation window has expired."}`.
Refreshing or editing a booking does not restart the deadline. Status remains
read-only in PATCH requests.

Celery Beat schedules `bookings.tasks.expire_pending_bookings` every five
minutes. It marks expired pending customer bookings `expired`, records the
original deadline as `expired_at`, and removes their DriverSlot. Booking and
item history remain available. Both availability and allocation ignore expired
holds at the deadline, even before cleanup runs. Completed bookings continue
to consume their original slot capacity.

Creation locks the existing `DriverProfile` row before counting reservations.
Confirmation, cancellation and cleanup lock the booking first, then its driver
row. Reassignment locks old and new drivers in ID order and preserves
pending customer status. All reservation mutations must use these services;
direct ORM or admin changes to reservation fields bypass the capacity protocol.

Install `requirements.txt` and set `CELERY_BROKER_URL` for your broker (default:
`redis://localhost:6379/0`). Run a broker, a worker, and one Beat scheduler:

```shell
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

The API enforces expiration even when the worker or Beat is unavailable.

Cleanup processes at most 500 records per run, skips rows locked by another
worker, and safely resumes after partial progress. Transient database failures
retry up to five times with exponential backoff and jitter. Each successful run
records a heartbeat and logs processed/backlog counts; remaining backlog is
logged as a warning. Celery logs task failures. Tasks have a 240-second soft and
270-second hard time limit.

Run `python manage.py check_booking_cleanup` from an independent monitoring
system every five minutes, and alert on a nonzero exit. It detects missing or
stale heartbeats (15 minutes), overdue backlog (15 minutes after expiration),
and database failures. Run this outside Celery so a stopped scheduler or worker
can be detected. Alert routing belongs to the deployment monitoring system.

Before deployment, create/apply migrations for
`BookingRequest`, `BookingCleanupState`, and Booking's expired status/timestamp
and cleanup index. No migrations were generated here. Restart workers and Beat
with the new task name; run one Beat scheduler. Validate concurrent allocation,
confirmation at the deadline, retries, cancellation, reassignment and overlapping
cleanup against PostgreSQL after migrating; SQLite cannot verify row locks.

## Select materials

- Dry waste: use the existing `/api/v1/catalog/waste-types/` catalog hierarchy.
  Submit selected WasteSubCategory IDs with each item's estimated weight.
- Scrap: `GET /api/v1/catalog/scrap-materials/` returns active materials and
  their price per kg. Administrators maintain these prices; no example prices
  are seeded from the screenshots.

## Preview scrap earnings

`POST /api/v1/bookings/quote/`

```json
{
  "scrap_items": [
    {"material": 1, "estimated_weight": "4.00"},
    {"material": 2, "estimated_weight": "2.00"}
  ]
}
```

Returns item names, weights, current rates, rounded item payouts, and the total
`estimated_payout`. Booking creation calculates the total from catalog prices and
stores it on Booking. Items store material, an editable name, estimated weight,
and estimated payout. Editing a weight recalculates its payout at the current
material rate; renaming an item does not rename the catalog material.
Actual payout/weight settlement is separate.

## Select address, date, and slot

Use `/api/v1/customers/addresses/` for addresses.

`GET /api/v1/catalog/time-slots/?date=2026-10-01`

The `/time-slots/availability/?date=2026-10-01` endpoint returns the same data.
Without `date`, the standard list returns reusable slot definitions only.

Returns active slots with `is_available` and calculated `remaining_capacity`.
Disable slots with `is_available: false` and label them "Unavailable".
Capacity is four bookings per eligible driver per slot/date. Unavailable or
inactive drivers/users are excluded. Already-started slots are unavailable.
Availability is advisory; booking creation rechecks capacity under a driver row lock.

## Create dry waste booking

`POST /api/v1/bookings/`

```json
{
  "booking_type": "waste",
  "address": 1,
  "slot": 1,
  "scheduled_date": "2026-10-01",
  "waste_items": [
    {"subcategory": 1, "estimated_weight": "4.00"},
    {"subcategory": 2, "estimated_weight": "2.00"}
  ],
  "note": "Please call on arrival."
}
```

The server derives the booking total from item weights. A supplied booking-level
weight is ignored.

## Create scrap booking

`POST /api/v1/bookings/`

```json
{
  "booking_type": "scrap",
  "address": 1,
  "slot": 1,
  "scheduled_date": "2026-10-01",
  "scrap_items": [
    {"material": 1, "estimated_weight": "4.00"},
    {"material": 2, "estimated_weight": "2.00"}
  ],
  "note": "Please call on arrival."
}
```

The server sums scrap weights and calculates earnings. Both flows choose the
first eligible driver with capacity in ID order, lock with `select_for_update`,
and create Booking, DriverSlot, and items in one transaction. Success returns
HTTP 201 and `status: "pending"` for customers. Full slots return HTTP 400 without creating
partial records. PostgreSQL provides the production row-lock guarantee.

Responses and `GET /api/v1/bookings/{id}/` include `reference`, `note`,
`address_details`, `slot_details`, `waste_items`, `scrap_items`, and
`estimated_payout`. The reference is formatted as `WKL-<creation year>-<id>`.

Admin requests use the authenticated customer's profile; source is set to `admin` and they do not
consume driver capacity. Customers cannot choose another customer or a driver.

Confirmed bookings support `PATCH` of `note` on the parent record. Item endpoints
support POST, PUT, PATCH, and DELETE:

- `/api/v1/booking-waste-items/`: create with `booking`, `subcategory`, and
  `estimated_weight`; edit subcategory and weight on `/{id}/`.
- `/api/v1/scrap-booking-items/`: create with `scrap_booking`, `material`,
  `estimated_weight`, and optional `name`; edit name and weight on `/{id}/`.

An item cannot be moved to another booking. Each mutation locks its parent Booking
and recalculates the total weight atomically. Scrap mutations also update the total
payout. Deleting the last item sets totals to zero. Customers can only manage
their own items. Django admin item edits use the same services.

Common creation is in `services.py`; waste operations are in `waste_services.py`
and scrap operations/quotes in `scrap_services.py`. Direct booking deletion is
disabled. Cancellation uses `POST /api/v1/bookings/{id}/cancel/` and releases
capacity. Rescheduling remains separate work.

Schema changes require migrations before these endpoints can run against an
existing database. No migrations are included in this change.
