"""
auth.py — Authentication blueprint.

Endpoints:
    GET/POST  /register   → register.html
    GET/POST  /login      → login.html
    GET       /logout     → logs out, redirects home
"""

from functools import wraps

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for
)
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from db import fetch_one, insert

auth_bp = Blueprint("auth", __name__)


# ============================================================
#  Role guard decorator
#  Usage: @role_required("admin")  or  @role_required("organizer", "admin")
# ============================================================
def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def role_dashboard_url(role):
    """Return the correct dashboard endpoint name for a role."""
    if role == "admin":
        return url_for("dashboards.admin_dashboard")
    if role == "organizer":
        return url_for("dashboards.organizer_dashboard")
    return url_for("dashboards.participant_dashboard")
    # NOTE: previously url_for("admin_dashboard") / "organizer_dashboard" /
    # "participant_dashboard" with no blueprint prefix — these routes live
    # in dashboards.py's dashboards_bp, so they need the "dashboards." prefix.


# ============================================================
#  REGISTER
# ============================================================
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "participant")

        # --- Validation ---
        if role not in ("participant", "organizer"):
            role = "participant"  # admin accounts can never self-register
        if not name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("auth.register"))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("auth.register"))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))
        if fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("auth.register"))

        # --- Create user ---
        user_id = insert(
            """INSERT INTO users (name, email, phone, password_hash, role)
               VALUES (%s, %s, %s, %s, %s)""",
            (name, email, phone, generate_password_hash(password), role),
        )

        # Auto-login after registration
        from app import User  # local import avoids circular dependency
        login_user(User(user_id, name, email, role))

        flash(f"Welcome to EventHub, {name}! 🎉", "success")
        return redirect(role_dashboard_url(role))

    return render_template("register.html")


# ============================================================
#  LOGIN
# ============================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        row = fetch_one("SELECT * FROM users WHERE email = %s", (email,))
        if not row or not check_password_hash(row["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))

        from app import User  # local import avoids circular dependency
        login_user(User(row["id"], row["name"], row["email"], row["role"]))

        flash(f"Welcome back, {row['name']}! 👋", "success")

        # If the user was redirected here from a protected page, send them back
        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)
        return redirect(role_dashboard_url(row["role"]))

    return render_template("login.html")


# ============================================================
#  LOGOUT
# ============================================================
@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))  