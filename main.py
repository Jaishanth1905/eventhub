"""
main.py — Public routes.

    GET  /                     → index.html
    GET  /events               → events.html  (search q, category, sort)
    GET  /events/<id>          → event_details.html
    GET  /events/<id>/register → creates registration → payment page OR ticket
"""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from db import fetch_one, fetch_all, insert
from utils import generate_ticket_code, generate_qr_image, timedelta_to_time

main_bp = Blueprint("main", __name__)


# ============================================================
#  HOME
# ============================================================
@main_bp.route("/")
def index():
    return render_template("index.html")


# ============================================================
#  BROWSE / SEARCH / FILTER EVENTS
# ============================================================
@main_bp.route("/events")
def events():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "date")

    query = """
        SELECT e.id, e.title, e.category, e.poster, e.fee, e.capacity,
               e.start_datetime AS event_date,
               e.start_datetime AS event_time,
               COALESCE(v.name, e.venue) AS venue_name,
               u.name AS organizer_name,
               (e.capacity - COUNT(r.id)) AS seats_left
        FROM events e
        LEFT JOIN venues v      ON v.name = e.venue
        LEFT JOIN users u       ON u.id  = e.organizer_id
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE e.approval_state = 'approved'
    """
    params = []

    if q:
        query += " AND (e.title LIKE %s OR e.description LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        query += " AND e.category = %s"
        params.append(category)

    query += " GROUP BY e.id"
    if sort == "fee_low":
        query += " ORDER BY e.fee ASC"
    elif sort == "fee_high":
        query += " ORDER BY e.fee DESC"
    else:
        query += " ORDER BY e.start_datetime ASC"

    return render_template("events.html", events=fetch_all(query, tuple(params)))


# ============================================================
#  EVENT DETAILS
# ============================================================
@main_bp.route("/events/<int:event_id>")
def event_details(event_id):
    event = fetch_one(
        """
        SELECT e.*,
               e.start_datetime AS event_date,
               e.start_datetime AS event_time,
               e.registration_deadline AS deadline,
               COALESCE(v.name, e.venue) AS venue_name,
               u.name AS organizer_name,
               (e.capacity - COUNT(r.id)) AS seats_left
        FROM events e
        LEFT JOIN venues v        ON v.name = e.venue
        LEFT JOIN users u         ON u.id  = e.organizer_id
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE e.id = %s AND e.approval_state = 'approved'
        GROUP BY e.id
        """,
        (event_id,),
    )
    if not event:
        flash("Event not found or not published yet.", "warning")
        return redirect(url_for("main.events"))

    sessions = fetch_all(
        """SELECT * FROM event_sessions
           WHERE event_id = %s
           ORDER BY session_date ASC, start_time ASC""",
        (event_id,),
    )
    # PyMySQL returns TIME columns as timedelta, not time — convert so
    # the template's .strftime() calls on s.start_time/s.end_time work.
    for s in sessions:
        s["start_time"] = timedelta_to_time(s["start_time"])
        s["end_time"] = timedelta_to_time(s["end_time"])

    already_registered = False
    if current_user.is_authenticated:
        already_registered = bool(
            fetch_one(
                "SELECT id FROM registrations WHERE event_id = %s AND user_id = %s",
                (event_id, current_user.id),
            )
        )

    return render_template(
        "event_details.html",
        event=event,
        sessions=sessions,
        already_registered=already_registered,
    )


# ============================================================
#  REGISTER FOR EVENT
# ============================================================
@main_bp.route("/events/<int:event_id>/register")
def register_event(event_id):
    # --- Login gate ---
    if not current_user.is_authenticated:
        flash("Please log in to register for this event.", "warning")
        return redirect(url_for("auth.login", next=request.path))

    if current_user.role != "participant":
        flash("Only participant accounts can register for events.", "danger")
        return redirect(url_for("main.event_details", event_id=event_id))

    # --- Event must be approved/published ---
    event = fetch_one(
        "SELECT * FROM events WHERE id = %s AND approval_state = 'approved'",
        (event_id,),
    )
    if not event:
        flash("This event is not available.", "warning")
        return redirect(url_for("main.events"))

    # --- Deadline check ---
    deadline = event["registration_deadline"]
    if deadline and deadline < date.today():
        flash("The registration deadline has passed. 😢", "danger")
        return redirect(url_for("main.event_details", event_id=event_id))

    # --- Duplicate check ---
    existing = fetch_one(
        "SELECT id FROM registrations WHERE event_id = %s AND user_id = %s",
        (event_id, current_user.id),
    )
    if existing:
        flash("You are already registered for this event.", "info")
        return redirect(url_for("participant.view_ticket", registration_id=existing["id"]))

    # --- Capacity check ---
    count = fetch_one(
        "SELECT COUNT(*) AS c FROM registrations WHERE event_id = %s", (event_id,)
    )["c"]
    if event["capacity"] and count >= event["capacity"]:
        flash("Sorry, this event is sold out! 😢", "danger")
        return redirect(url_for("main.event_details", event_id=event_id))

    # --- Create registration + QR ticket ---
    ticket = generate_ticket_code()
    qr_filename = generate_qr_image(ticket)
    reg_id = insert(
        """INSERT INTO registrations (event_id, user_id, status, ticket_code, qr_code)
           VALUES (%s, %s, 'confirmed', %s, %s)""",
        (event_id, current_user.id, ticket, qr_filename),
    )

    # --- Paid? → sandbox payment. Free? → straight to ticket ---
    if event["fee"] and float(event["fee"]) > 0:
        return redirect(url_for("participant.payment", registration_id=reg_id))

    flash("Registration confirmed! Your QR ticket is ready 🎫", "success")
    return redirect(url_for("participant.view_ticket", registration_id=reg_id))