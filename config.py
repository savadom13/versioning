
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    _database_url = os.environ.get(
        "DATABASE_URL",
        "mysql://mysql:mysql@127.0.0.1:3307/versioning"  # default for demo; replace with MySQL in production
    )
    if _database_url.startswith("mysql://"):
        _database_url = _database_url.replace("mysql://", "mysql+pymysql://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
