"""
dashboards.py — Role-specific dashboard/overview pages.

    GET /admin/dashboard        -> dashboard_admin.html        (role: admin)
    GET /organizer/dashboard    -> dashboard_organizer.html    (role: organizer)
    GET /participant/dashboard  -> dashboard_participant.html  (role: participant)
"""

from flask import Blueprint, render_template, url_for
from flask_login import current_user

from auth import role_required
from db import fetch_all, fetch_one

dashboards_bp = Blueprint("dashboards", __name__)


# ============================================================
#  ADMIN DASHBOARD
# ============================================================
@dashboards_bp.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    stats = {
        "total_events": fetch_one("SELECT COUNT(*) AS c FROM events")["c"],
        "total_users": fetch_one("SELECT COUNT(*) AS c FROM users")["c"],
        "total_registrations": fetch_one("SELECT COUNT(*) AS c FROM registrations")["c"],
        "revenue": fetch_one(
            "SELECT COALESCE(SUM(amount), 0) AS c FROM payments WHERE status = 'success'"
        )["c"],
    }

    pending_rows = fetch_all(
        """
        SELECT e.id, e.title, e.category, e.start_datetime, u.name AS organizer_name
        FROM events e
        JOIN users u ON u.id = e.organizer_id
        WHERE e.approval_state = 'pending'
        ORDER BY e.submitted_at ASC
        """
    )
    pending_events = [
        {
            "title": row["title"],
            "organizer_name": row["organizer_name"],
            "category": row["category"],
            "date": row["start_datetime"].strftime("%d %b %Y") if row["start_datetime"] else "TBD",
            "approve_url": url_for("admin.approve_event", event_id=row["id"]),
            "reject_url": url_for("admin.reject_event", event_id=row["id"]),
        }
        for row in pending_rows
    ]

    recent_rows = fetch_all(
        """
        SELECT r.status, r.created_at, u.name AS participant_name, e.title AS event_title
        FROM registrations r
        JOIN users u  ON u.id = r.user_id
        JOIN events e ON e.id = r.event_id
        ORDER BY r.created_at DESC
        LIMIT 10
        """
    )
    recent_registrations = [
        {
            "participant_name": row["participant_name"],
            "event_title": row["event_title"],
            "created_at": row["created_at"].strftime("%d %b %Y, %I:%M %p") if row["created_at"] else "N/A",
            "status": (row["status"] or "confirmed").title(),
        }
        for row in recent_rows
    ]

    return render_template(
        "dashboard_admin.html",
        stats=stats,
        pending_events=pending_events,
        recent_registrations=recent_registrations,
    )


# ============================================================
#  ORGANIZER DASHBOARD
# ============================================================
@dashboards_bp.route("/organizer/dashboard")
@role_required("organizer")
def organizer_dashboard():
    organizer_id = current_user.id

    stats = {
        "total_events": fetch_one(
            "SELECT COUNT(*) AS c FROM events WHERE organizer_id = %s", (organizer_id,)
        )["c"],
        "approved_events": fetch_one(
            "SELECT COUNT(*) AS c FROM events WHERE organizer_id = %s AND approval_state = 'approved'",
            (organizer_id,),
        )["c"],
        "pending_events": fetch_one(
            "SELECT COUNT(*) AS c FROM events WHERE organizer_id = %s AND approval_state = 'pending'",
            (organizer_id,),
        )["c"],
        "total_registrations": fetch_one(
            """SELECT COUNT(*) AS c FROM registrations r
               JOIN events e ON e.id = r.event_id
               WHERE e.organizer_id = %s""",
            (organizer_id,),
        )["c"],
    }

    rows = fetch_all(
        """SELECT id, title, venue, start_datetime, approval_state
           FROM events WHERE organizer_id = %s
           ORDER BY start_datetime DESC""",
        (organizer_id,),
    )
    events = [
        {
            "title": row["title"],
            "date": row["start_datetime"].strftime("%d %b %Y") if row["start_datetime"] else "TBD",
            "venue": row["venue"] or "TBD",
            "approval_status": (row["approval_state"] or "draft").title(),
            "manage_url": url_for("organizer_bp.edit_event", event_id=row["id"]),
            "registrations_url": url_for("organizer_bp.event_participants", event_id=row["id"]),
            # No dedicated analytics view yet — reuse the participants page for now.
            "analytics_url": url_for("organizer_bp.event_participants", event_id=row["id"]),
        }
        for row in rows
    ]

    return render_template("dashboard_organizer.html", stats=stats, events=events)


# ============================================================
#  PARTICIPANT DASHBOARD
# ============================================================
@dashboards_bp.route("/participant/dashboard")
@role_required("participant")
def participant_dashboard():
    user_id = current_user.id

    stats = {
        "upcoming_count": fetch_one(
            """SELECT COUNT(*) AS c FROM registrations r
               JOIN events e ON e.id = r.event_id
               WHERE r.user_id = %s AND e.start_datetime >= NOW()""",
            (user_id,),
        )["c"],
        "attended_count": fetch_one(
            "SELECT COUNT(*) AS c FROM registrations WHERE user_id = %s AND attendance_status = 'present'",
            (user_id,),
        )["c"],
        "certificate_count": fetch_one(
            "SELECT COUNT(*) AS c FROM registrations WHERE user_id = %s AND certificate_issued = 1",
            (user_id,),
        )["c"],
    }

    upcoming_rows = fetch_all(
        """
        SELECT r.status, e.title AS event_title, e.start_datetime AS event_date,
               COALESCE(v.name, e.venue) AS venue
        FROM registrations r
        JOIN events e      ON e.id = r.event_id
        LEFT JOIN venues v ON v.name = e.venue
        WHERE r.user_id = %s AND e.start_datetime >= NOW()
        ORDER BY e.start_datetime ASC
        LIMIT 5
        """,
        (user_id,),
    )
    upcoming_registrations = [
        {
            "event_title": row["event_title"],
            "event_date": row["event_date"].strftime("%d %b %Y") if row["event_date"] else "TBD",
            "venue": row["venue"] or "TBD",
            "status": (row["status"] or "registered").title(),
        }
        for row in upcoming_rows
    ]

    recent_rows = fetch_all(
        """
        SELECT e.title AS event_title, r.attendance_time, r.certificate_issued
        FROM registrations r
        JOIN events e ON e.id = r.event_id
        WHERE r.user_id = %s AND r.attendance_status = 'present'
        ORDER BY r.attendance_time DESC
        LIMIT 5
        """,
        (user_id,),
    )
    recent_registrations = [
        {
            "event_title": row["event_title"],
            "attended_on": row["attendance_time"].strftime("%d %b %Y") if row["attendance_time"] else "Date unavailable",
            "certificate_status": "Certificate issued" if row["certificate_issued"] else "Certificate not issued",
        }
        for row in recent_rows
    ]

    return render_template(
        "dashboard_participant.html",
        stats=stats,
        upcoming_registrations=upcoming_registrations,
        recent_registrations=recent_registrations,
    )