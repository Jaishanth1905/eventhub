from flask import Blueprint, abort, render_template
 
from db import fetch_one
 
ticket_portal_bp = Blueprint("ticket_portal", __name__)
 
 
@ticket_portal_bp.route("/t/<ticket_code>")
def ticket_page(ticket_code):
    t = fetch_one(
        """
        SELECT r.id, r.ticket_code, r.qr_code, r.status, r.payment_status,
               r.attendance_status,
               u.name AS participant_name,
               e.title, e.category, e.description, e.venue, e.poster,
               e.start_datetime
        FROM registrations r
        JOIN users u ON u.id = r.user_id
        JOIN events e ON e.id = r.event_id
        WHERE r.ticket_code = %s
        """,
        (ticket_code,),
    )
    if not t:
        abort(404)
    return render_template("ticket_portal.html", t=t)