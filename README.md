
# Flask Production-Grade Entity Versioning Demo

## Features
- Multi-entity versioning (signals and assets) with audit trail
- Snapshot + SHA256 hash protection
- Generic SQLAlchemy event-based versioning for all entities
- **Optimistic locking at ORM level:** versioned models use SQLAlchemy `version_id_col` (lock_version). The view checks client-supplied `lock_version` before modifying; on flush, UPDATE/DELETE include `WHERE lock_version = :current` and SQLAlchemy raises `StaleDataError` (mapped to 409) if the row was changed elsewhere. No version is created when fields are unchanged (handled in `models.py`).
- Tailwind CSS UI
- MySQL via PyMySQL
- Demo active user selector (used for `created_by` / `updated_by`)

## Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
flask --app app/app.py db upgrade
python app/app.py
```

Open: http://127.0.0.1:8000

## MySQL (Production)

Set environment variable:

DATABASE_URL=mysql+pymysql://user:password@localhost/dbname

## Optimistic locking

- Forms must send `lock_version` (hidden input) so the server can reject stale updates.
- For new versioned entities: add the model to `ENTITY_MODELS`, call `_check_lock_version(entity, _expected_lock_version_from_request())` in edit/delete views before modifying, and include `lock_version` in forms. The ORM uses `version_id_col` so UPDATE/DELETE check the version at flush; conflicts raise `StaleDataError` → 409.
- **Limitation:** Optimistic locking via `version_id_col` applies only to per-row flush (load → modify → commit). Bulk operations (`Query.update()` / `Query.delete()` without loading entities) do not perform version checks.

## Migrations

```bash
# First-time only (if you create a clean repo without migrations folder)
flask --app app/app.py db init

# Generate next migration after model changes
flask --app app/app.py db migrate -m "describe change"

# Apply migrations
flask --app app/app.py db upgrade
```
