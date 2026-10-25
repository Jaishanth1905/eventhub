"""
admin.py — Admin blueprint.

Event approval actions used by dashboard_admin.html's Approve / Reject buttons.
"""

from flask import Blueprint, flash, redirect, url_for

from auth import role_required
from db import execute, fetch_one

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/events/<int:event_id>/approve", methods=["POST"])
@role_required("admin")
def approve_event(event_id):
    event = fetch_one("SELECT id FROM events WHERE id = %s", (event_id,))
    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for("dashboards.admin_dashboard"))

    execute("UPDATE events SET approval_state = 'approved' WHERE id = %s", (event_id,))
    flash("Event approved and published. ✅", "success")
    return redirect(url_for("dashboards.admin_dashboard"))


@admin_bp.route("/admin/events/<int:event_id>/reject", methods=["POST"])
@role_required("admin")
def reject_event(event_id):
    event = fetch_one("SELECT id FROM events WHERE id = %s", (event_id,))
    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for("dashboards.admin_dashboard"))

    execute("UPDATE events SET approval_state = 'rejected' WHERE id = %s", (event_id,))
    flash("Event rejected.", "info")
    return redirect(url_for("dashboards.admin_dashboard"))