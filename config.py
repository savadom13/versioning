
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///app.db"  # default for demo; replace with MySQL in production
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
