import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-dev-secret")

    # MySQL
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB = os.getenv("MYSQL_DB", "eventhub")

    # Uploads
    UPLOAD_FOLDER = os.path.join("static", "uploads")
    QR_FOLDER = os.path.join("static", "uploads", "qr")
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4 MB

    # Default admin credentials (auto-created on first run)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@eventhub.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")