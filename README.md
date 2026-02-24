
# Flask Production-Grade Entity Versioning Demo

## Features
- Multi-entity versioning (signals and assets) with audit trail
- Snapshot + SHA256 hash protection
- Generic SQLAlchemy event-based versioning for all entities
- **Automatic optimistic locking:** edit/delete routes use `@require_optimistic_lock(Model)`; the actual version check runs in SQLAlchemy `before_flush`, so views only load, modify, and commit. No version is created when fields are unchanged (handled in `models.py`).
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
- For new versioned entities: add the model to `ENTITY_MODELS`, use `@require_optimistic_lock(YourModel)` on edit/delete views, and include `lock_version` in forms. The check is enforced in `before_flush` in `models.py`.

## Migrations

```bash
# First-time only (if you create a clean repo without migrations folder)
flask --app app/app.py db init

# Generate next migration after model changes
flask --app app/app.py db migrate -m "describe change"

# Apply migrations
flask --app app/app.py db upgrade
```
