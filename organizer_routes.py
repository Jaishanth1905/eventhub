from __future__ import annotations
 
import os
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Iterable, Optional
 
import pymysql.cursors
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
 
from utils import timedelta_to_time
 
organizer_bp = Blueprint("organizer_bp", __name__, template_folder="templates")
 
 
def get_current_user() -> Optional[Dict[str, Any]]:
    """Integration hook for current user lookup."""
    if hasattr(current_app, "login_manager"):
        try:
            from flask_login import current_user  # type: ignore
 
            if getattr(current_user, "is_authenticated", False):
                return {
                    "id": getattr(current_user, "id", None),
                    "role": getattr(current_user, "role", None),
                    "name": getattr(current_user, "name", ""),
                }
        except Exception:
            return None
    return None
 
 
def organizer_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Please log in to access organizer workspace.", "warning")
            return redirect(url_for("auth.login"))
        if user.get("role") != "organizer":
            abort(403)
        return view_func(*args, **kwargs)
 
    return wrapped
 
 
def _get_db():
    mysql_ext = current_app.extensions.get("mysql")
    if mysql_ext is None or not hasattr(mysql_ext, "connection"):
        raise RuntimeError("MySQL extension is not configured at current_app.extensions['mysql']")
    return mysql_ext.connection
 
 
def _fetch_all(query: str, params: Iterable[Any] = ()) -> list:
    cursor = _get_db().cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    finally:
        cursor.close()
 
 
def _fetch_one(query: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
    cursor = _get_db().cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute(query, tuple(params))
        return cursor.fetchone()
    finally:
        cursor.close()
 
 
def _execute(query: str, params: Iterable[Any] = ()) -> int:
    cursor = _get_db().cursor()
    try:
        cursor.execute(query, tuple(params))
        return cursor.rowcount
    finally:
        cursor.close()
 
 
def _insert(query: str, params: Iterable[Any] = ()) -> int:
    cursor = _get_db().cursor()
    try:
        cursor.execute(query, tuple(params))
        return cursor.lastrowid
    finally:
        cursor.close()
 
 
def _event_owned_by(event_id: int, organizer_id: int) -> bool:
    return bool(_fetch_one("SELECT id FROM events WHERE id = %s AND organizer_id = %s", (event_id, organizer_id)))
 
 
# ============================================================
#  CREATE EVENT
# ============================================================
@organizer_bp.route("/events/create", methods=["GET", "POST"])
@organizer_required
def create_event():
    user = get_current_user()
 
    if request.method == "POST":
        form = request.form
 
        poster_filename = None
        poster_file = request.files.get("poster")
        if poster_file and poster_file.filename:
            poster_filename = secure_filename(poster_file.filename)
            poster_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], poster_filename))
 
        fee_type = "paid" if form.get("is_paid") == "paid" else "free"
        fee = float(form.get("fee", "0") or 0) if fee_type == "paid" else 0.0
 
        event_date = form.get("date", "").strip()
        event_time = form.get("time", "").strip()
        start_datetime = f"{event_date} {event_time}:00" if event_date and event_time else None
 
        db = _get_db()
        try:
            new_id = _insert(
                """
                INSERT INTO events
                    (organizer_id, title, category, description, venue, poster,
                     start_datetime, registration_deadline, capacity, fee_type, fee, approval_state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
                """,
                (
                    user["id"],
                    form.get("title", "").strip(),
                    form.get("category", "").strip(),
                    form.get("description", "").strip(),
                    form.get("venue", "").strip(),
                    poster_filename,
                    start_datetime,
                    form.get("registration_deadline", "").strip() or None,
                    int(form.get("capacity", "0") or 0) or None,
                    fee_type,
                    fee,
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
 
        flash("Event created as a draft. Add a schedule, then submit it for approval.", "success")
        return redirect(url_for("organizer_bp.edit_event", event_id=new_id))
 
    return render_template("create_event.html")
 
 
@organizer_bp.route("/events")
@organizer_required
def organizer_workspace():
    user = get_current_user()
    events = _fetch_all(
        """
        SELECT e.id, e.title, e.category, e.venue, e.start_datetime, e.capacity, e.approval_state,
               COALESCE(COUNT(r.id), 0) AS registrations_count
        FROM events e
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE e.organizer_id = %s
        GROUP BY e.id
        ORDER BY e.start_datetime DESC
        """,
        (user["id"],),
    )
    return render_template("organizer_event_workspace.html", events=events, organizer=user)
 
 
@organizer_bp.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@organizer_required
def edit_event(event_id: int):
    user = get_current_user()
    if not _event_owned_by(event_id, user["id"]):
        abort(404)
 
    if request.method == "POST":
        form = request.form
        action = form.get("action", "save_draft").strip()
        next_state = "pending" if action == "submit" else "draft"
        db = _get_db()
        try:
            _execute(
                """
                UPDATE events
                SET title=%s, category=%s, venue=%s, description=%s, start_datetime=%s, capacity=%s,
                    registration_deadline=%s, fee_type=%s, fee=%s, poster=%s, approval_state=%s, updated_at=%s
                WHERE id=%s AND organizer_id=%s
                """,
                (
                    form.get("title", "").strip(),
                    form.get("category", "").strip(),
                    form.get("venue", "").strip(),
                    form.get("description", "").strip(),
                    form.get("start_datetime", "").strip() or None,
                    int(form.get("capacity", "0") or 0) or None,
                    form.get("registration_deadline", "").strip() or None,
                    form.get("fee_type", "free").strip(),
                    float(form.get("fee", "0") or 0),
                    form.get("poster", "").strip() or None,
                    next_state,
                    datetime.utcnow(),
                    event_id,
                    user["id"],
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        if action == "submit":
            return redirect(url_for("organizer_bp.submit_for_approval", event_id=event_id))
        flash("Event draft updated.", "success")
        return redirect(url_for("organizer_bp.edit_event", event_id=event_id))
 
    event = _fetch_one("SELECT * FROM events WHERE id = %s AND organizer_id = %s", (event_id, user["id"]))
    venues = _fetch_all("SELECT id, name, location, capacity FROM venues WHERE is_active = 1 ORDER BY name ASC")
    return render_template("edit_event.html", event=event, venues=venues)
 
 
@organizer_bp.route("/events/<int:event_id>/schedule", methods=["GET", "POST"])
@organizer_required
def manage_schedule(event_id: int):
    user = get_current_user()
    if not _event_owned_by(event_id, user["id"]):
        abort(404)
    if request.method == "POST":
        form = request.form
        db = _get_db()
        try:
            _execute(
                """
                INSERT INTO event_sessions (event_id, session_name, speaker, session_date, start_time, end_time, venue)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_id,
                    form.get("session_name", "").strip(),
                    form.get("speaker", "").strip(),
                    form.get("session_date", "").strip(),
                    form.get("start_time", "").strip(),
                    form.get("end_time", "").strip(),
                    form.get("venue", "").strip(),
                ),
            )
            db.commit()
            flash("Session added.", "success")
        except Exception:
            db.rollback()
            raise
        return redirect(url_for("organizer_bp.manage_schedule", event_id=event_id))
 
    event = _fetch_one(
        "SELECT id, title, start_datetime, approval_state FROM events WHERE id = %s AND organizer_id = %s",
        (event_id, user["id"]),
    )
    sessions = _fetch_all(
        """
        SELECT id, session_name, speaker, session_date, start_time, end_time, venue
        FROM event_sessions
        WHERE event_id = %s
        ORDER BY session_date ASC, start_time ASC
        """,
        (event_id,),
    )
    # PyMySQL returns TIME columns as timedelta, not time — convert so
    # the template can format them consistently.
    for s in sessions:
        s["start_time"] = timedelta_to_time(s["start_time"])
        s["end_time"] = timedelta_to_time(s["end_time"])
 
    return render_template("manage_schedule.html", event=event, sessions=sessions)
 
 
@organizer_bp.route("/events/<int:event_id>/sessions/<int:session_id>/delete", methods=["POST"])
@organizer_required
def delete_session(event_id: int, session_id: int):
    user = get_current_user()
    if not _event_owned_by(event_id, user["id"]):
        abort(404)
    db = _get_db()
    try:
        _execute(
            """
            DELETE es FROM event_sessions es
            INNER JOIN events e ON e.id = es.event_id
            WHERE es.id = %s AND es.event_id = %s AND e.organizer_id = %s
            """,
            (session_id, event_id, user["id"]),
        )
        db.commit()
        flash("Session removed.", "success")
    except Exception:
        db.rollback()
        raise
    return redirect(url_for("organizer_bp.manage_schedule", event_id=event_id))
 
 
@organizer_bp.route("/events/<int:event_id>/submit", methods=["GET", "POST"])
@organizer_required
def submit_for_approval(event_id: int):
    user = get_current_user()
    if not _event_owned_by(event_id, user["id"]):
        abort(404)
    event = _fetch_one("SELECT id, title, approval_state FROM events WHERE id = %s AND organizer_id = %s", (event_id, user["id"]))
    if request.method == "POST":
        db = _get_db()
        try:
            _execute(
                "UPDATE events SET approval_state=%s, submitted_at=%s, updated_at=%s WHERE id=%s AND organizer_id=%s",
                ("pending", datetime.utcnow(), datetime.utcnow(), event_id, user["id"]),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    return render_template("submission_confirmation.html", event=event)
 
 
@organizer_bp.route("/events/<int:event_id>/participants")
@organizer_required
def event_participants(event_id: int):
    user = get_current_user()
    if not _event_owned_by(event_id, user["id"]):
        abort(404)
    event = _fetch_one("SELECT id, title, start_datetime FROM events WHERE id=%s AND organizer_id=%s", (event_id, user["id"]))
    participants = _fetch_all(
        """
        SELECT r.id, r.status, r.payment_status, r.attendance_status, r.ticket_code, r.created_at,
               u.name AS participant_name, u.email AS participant_email
        FROM registrations r
        LEFT JOIN users u ON u.id = r.user_id
        WHERE r.event_id = %s
        ORDER BY r.created_at DESC
        """,
        (event_id,),
    )
    return render_template("event_participants.html", event=event, participants=participants)
 
 
# ============================================================
#  SCAN QR / MARK ATTENDANCE
# ============================================================
@organizer_bp.route("/events/<int:event_id>/scan", methods=["GET", "POST"])
@organizer_required
def scan_qr(event_id: int):
    user = get_current_user()
    if not _event_owned_by(event_id, user["id"]):
        abort(404)
 
    event = _fetch_one(
        "SELECT id, title, start_datetime FROM events WHERE id = %s AND organizer_id = %s",
        (event_id, user["id"]),
    )
 
    scan_result = None
    if request.method == "POST":
        qr_data = request.form.get("qr_data", "").strip()
        if "/t/" in qr_data:  # QR now holds a URL; keep only the ticket code
            qr_data = qr_data.rstrip("/").split("/")[-1]
 
        reg_id_guess = int(qr_data) if qr_data.isdigit() else -1
        registration = _fetch_one(
            """
            SELECT r.id, r.ticket_code, r.attendance_status, u.name AS participant_name
            FROM registrations r
            JOIN users u ON u.id = r.user_id
            WHERE r.event_id = %s AND (r.ticket_code = %s OR r.id = %s)
            """,
            (event_id, qr_data, reg_id_guess),
        )
 
        if not registration:
            scan_result = {
                "success": False,
                "message": "No matching ticket found for this event.",
            }
        elif registration["attendance_status"] == "present":
            scan_result = {
                "success": True,
                "attendee_name": registration["participant_name"],
                "registration_id": registration["id"],
                "message": "Already checked in earlier.",
                "attendance_state": "Present (duplicate scan)",
            }
        else:
            db = _get_db()
            try:
                _execute(
                    "UPDATE registrations SET attendance_status = 'present', attendance_time = %s WHERE id = %s",
                    (datetime.utcnow(), registration["id"]),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            scan_result = {
                "success": True,
                "attendee_name": registration["participant_name"],
                "registration_id": registration["id"],
                "message": "Checked in successfully! ✅",
                "attendance_state": "Present",
            }
 
    return render_template("scan_qr.html", event=event, scan_result=scan_result)
 
 
@organizer_bp.route("/venues")
@organizer_required
def manage_venues():
    venues = _fetch_all("SELECT id, name, location, capacity, is_active FROM venues ORDER BY name ASC")
    return render_template("manage_venues.html", venues=venues, filters={})
 
 
@organizer_bp.route("/venues/availability")
@organizer_required
def venue_availability():
    query_date = request.args.get("date", "").strip()
    start_time = request.args.get("start_time", "").strip()
    end_time = request.args.get("end_time", "").strip()
    venues = _fetch_all(
        """
        SELECT v.id, v.name, v.location, v.capacity, v.is_active,
               CASE
                   WHEN EXISTS (
                       SELECT 1 FROM event_sessions s
                       WHERE s.venue = v.name AND s.session_date = %s
                         AND ((s.start_time <= %s AND s.end_time > %s)
                           OR (s.start_time < %s AND s.end_time >= %s)
                           OR (s.start_time >= %s AND s.end_time <= %s))
                   ) THEN 0 ELSE 1 END AS is_available
        FROM venues v
        ORDER BY v.name ASC
        """,
        (query_date, start_time, start_time, end_time, end_time, start_time, end_time),
    )
    return render_template(
        "manage_venues.html",
        venues=venues,
        filters={"date": query_date, "start_time": start_time, "end_time": end_time},
    )
 
 
@organizer_bp.route("/venues/availability.json")
@organizer_required
def venue_availability_json():
    date = request.args.get("date", "").strip()
    start = request.args.get("start_time", "").strip()
    end = request.args.get("end_time", "").strip()
    results = _fetch_all(
        """
        SELECT v.id, v.name, v.location, v.capacity,
               CASE
                   WHEN EXISTS (
                       SELECT 1 FROM event_sessions s
                       WHERE s.venue = v.name AND s.session_date = %s
                         AND ((s.start_time <= %s AND s.end_time > %s)
                           OR (s.start_time < %s AND s.end_time >= %s)
                           OR (s.start_time >= %s AND s.end_time <= %s))
                   ) THEN 'unavailable' ELSE 'available' END AS availability
        FROM venues v
        ORDER BY v.name ASC
        """,
        (date, start, start, end, end, start, end),
    )
    return jsonify(results)