import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    _database_url = os.environ.get(
        "DATABASE_URL",
        "mysql://root:mysql@127.0.0.1:3307/versioning"  # default for demo; replace with MySQL in production
    )
    if _database_url.startswith("mysql://"):
        _database_url = _database_url.replace("mysql://", "mysql+pymysql://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 60 * 60 * 24))  # 24h default
    JWT_ALGORITHM = "HS256"

    # Demo auth (for development only; replace with real auth in production)
    DEMO_USERNAME = "test"
    DEMO_PASSWORD = "test"
