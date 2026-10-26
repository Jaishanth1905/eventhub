"""
EventHub — Application entry point.

Run:
    pip install -r requirements.txt
    python app.py

Note: make sure schema.sql is executed and .env is configured first.
"""

import os
import pymysql.cursors
from flask import Flask, render_template_string
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash

from config import Config
from mysql_ext import MySQL 

# ============================================================
#  Extensions
# ============================================================
mysql = MySQL()          
login_manager = LoginManager()


# ============================================================
#  User class for Flask-Login
# ============================================================
class User(UserMixin):
    def __init__(self, id, name, email, role):
        self.id = id
        self.name = name
        self.email = email
        self.role = role  # 'admin' | 'organizer' | 'participant'

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login calls this on every request to rebuild current_user."""
    cur = mysql.connection.cursor(pymysql.cursors.DictCursor)
    cur.execute(
        "SELECT id, name, email, role FROM users WHERE id = %s", (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    if row:
        return User(id=row["id"], name=row["name"], email=row["email"], role=row["role"])
    return None


# ============================================================
#  Admin auto-seeding
# ============================================================
def seed_admin():
    """Create the default admin account if none exists yet."""
    cur = mysql.connection.cursor(pymysql.cursors.DictCursor)
    cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    exists = cur.fetchone()
    if not exists:
        cur.execute(
            """INSERT INTO users (name, email, phone, password_hash, role)
               VALUES (%s, %s, %s, %s, 'admin')""",
            (
                "Administrator",
                Config.ADMIN_EMAIL,
                "0000000000",
                generate_password_hash(Config.ADMIN_PASSWORD, method="pbkdf2:sha256"),
            ),
        )
        mysql.connection.commit()
        print(f"[✔] Admin account created → {Config.ADMIN_EMAIL} / {Config.ADMIN_PASSWORD}")
    cur.close()


# ============================================================
#  Simple inline error pages
# ============================================================
ERROR_PAGE = """
<!DOCTYPE html><html><head><title>{{ code }}</title>
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}"></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh;">
  <div style="text-align:center;">
    <h1 class="gradient-text" style="font-size:80px;">{{ code }}</h1>
    <p style="color:var(--gray);margin:12px 0 28px;">{{ message }}</p>
    <a class="btn btn-primary" href="{{ url_for('main.index') }}">← Back to Home</a>
  </div>
</body></html>
"""


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template_string(ERROR_PAGE, code=403, message="You don't have permission to access this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template_string(ERROR_PAGE, code=404, message="Oops! This page doesn't exist."), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template_string(ERROR_PAGE, code=500, message="Something went wrong on our side."), 500


# ============================================================
#  App factory
# ============================================================
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Create upload folders
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["QR_FOLDER"], exist_ok=True)

    # Init extensions
    mysql.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    # ---- Blueprints ----
    from auth import auth_bp
    from main import main_bp
    from organizer_routes import organizer_bp
    from participant import participant_bp
    from admin import admin_bp
    from dashboards import dashboards_bp
    from ticket_portal import ticket_portal_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(participant_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(dashboards_bp)
    app.register_blueprint(ticket_portal_bp)
    app.register_blueprint(organizer_bp, url_prefix="/organizer")

    register_error_handlers(app)

    # Seed admin on first request
    with app.app_context():
        seed_admin()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=int(os.getenv("PORT", "5001")))