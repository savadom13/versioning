
# Flask Production-Grade Object Versioning Demo

## Features
- Object versioning with audit trail
- Snapshot + SHA256 hash protection
- SQLAlchemy event-based automatic versioning
- Tailwind CSS UI
- SQLite for demo (MySQL ready)

## Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app/app.py
```

Open: http://127.0.0.1:5000

## MySQL (Production)

Set environment variable:

DATABASE_URL=mysql+pymysql://user:password@localhost/dbname
