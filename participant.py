"""
participant.py — Participant blueprint.

Endpoints:
    GET   /my-registrations                          -> my_registrations.html
    GET   /ticket/<registration_id>                   -> view_ticket.html
    GET   /payment/<registration_id>                  -> payment.html
    POST  /payment/<registration_id>/process           -> process_payment (sandbox)
    GET   /payment/<registration_id>/success            -> payment_success.html
    GET   /feedback/<registration_id>                  -> feedback.html
    POST  /feedback/<registration_id>/submit             -> submit_feedback
    GET   /certificate/<registration_id>                -> certificate.html
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from auth import role_required
from db import execute, fetch_all, fetch_one, insert
from utils import generate_payment_id

participant_bp = Blueprint("participant", __name__)


# ============================================================
#  Helper — load a registration and make sure it belongs to
#  the logged-in participant. Aborts 404 otherwise (never
#  leaks whether the registration exists to someone else).
# ============================================================
def _get_own_registration(registration_id):
    reg = fetch_one(
        """
        SELECT r.*, e.title AS event_title, e.fee, e.fee_type,
               e.start_datetime AS event_date, e.start_datetime AS event_time,
               COALESCE(v.name, e.venue) AS venue_name,
               u.name AS participant_name
        FROM registrations r
        JOIN events e   ON e.id = r.event_id
        LEFT JOIN venues v ON v.name = e.venue
        JOIN users u    ON u.id = r.user_id
        WHERE r.id = %s
        """,
        (registration_id,),
    )
    if not reg or reg["user_id"] != current_user.id:
        abort(404)
    return reg


# ============================================================
#  MY REGISTRATIONS  (ticket list)
# ============================================================
@participant_bp.route("/my-registrations")
@role_required("participant")
def my_registrations():
    rows = fetch_all(
        """
        SELECT r.id, r.qr_code, r.payment_status, r.attendance_status,
               r.feedback_given, r.certificate_issued,
               e.id AS event_id, e.title AS event_title,
               e.start_datetime AS event_date, e.start_datetime AS event_time,
               COALESCE(v.name, e.venue) AS venue_name,
               p.amount AS amount
        FROM registrations r
        JOIN events e        ON e.id = r.event_id
        LEFT JOIN venues v   ON v.name = e.venue
        LEFT JOIN payments p ON p.registration_id = r.id AND p.status = 'success'
        WHERE r.user_id = %s
        ORDER BY e.start_datetime DESC
        """,
        (current_user.id,),
    )
    # Template checks reg.attended / reg.feedback_given as simple truthy flags.
    for row in rows:
        row["attended"] = row["attendance_status"] == "present"

    return render_template("my_registrations.html", registrations=rows)


# ============================================================
#  VIEW TICKET (QR code)
# ============================================================
@participant_bp.route("/ticket/<int:registration_id>")
@role_required("participant")
def view_ticket(registration_id):
    reg = _get_own_registration(registration_id)
    return render_template("view_ticket.html", registration=reg)


# ============================================================
#  PAYMENT PAGE
# ============================================================
@participant_bp.route("/payment/<int:registration_id>")
@role_required("participant")
def payment(registration_id):
    reg = _get_own_registration(registration_id)

    if reg["fee_type"] != "paid" or not reg["fee"] or float(reg["fee"]) <= 0:
        flash("This registration doesn't require payment.", "info")
        return redirect(url_for("participant.view_ticket", registration_id=registration_id))

    if reg["payment_status"] == "paid":
        flash("You've already paid for this event.", "info")
        return redirect(url_for("participant.view_ticket", registration_id=registration_id))

    event = {
        "title": reg["event_title"],
        "event_date": reg["event_date"],
        "venue_name": reg["venue_name"],
        # Cast to float — MySQL DECIMAL columns come back as decimal.Decimal
        # via PyMySQL, and payment.html multiplies this by float literals
        # (0.18, 1.18) for GST, which Python doesn't allow mixing.
        "fee": float(reg["fee"]) if reg["fee"] is not None else 0.0,
    }
    return render_template("payment.html", event=event, registration_id=registration_id)


# ============================================================
#  PROCESS PAYMENT (sandbox — always succeeds)
# ============================================================
@participant_bp.route("/payment/<int:registration_id>/process", methods=["POST"])
@role_required("participant")
def process_payment(registration_id):
    reg = _get_own_registration(registration_id)

    if reg["payment_status"] == "paid":
        return redirect(url_for("participant.payment_success", registration_id=registration_id))

    amount = round(float(reg["fee"]) * 1.18, 2)  # ticket fee + 18% GST, matches payment.html
    payment_ref = generate_payment_id()

    insert(
        """INSERT INTO payments (registration_id, payment_id, amount, status)
           VALUES (%s, %s, %s, 'success')""",
        (registration_id, payment_ref, amount),
    )
    execute(
        "UPDATE registrations SET payment_status = 'paid' WHERE id = %s",
        (registration_id,),
    )

    flash("Payment successful! Your ticket is ready 🎉", "success")
    return redirect(url_for("participant.payment_success", registration_id=registration_id))


# ============================================================
#  PAYMENT SUCCESS
# ============================================================
@participant_bp.route("/payment/<int:registration_id>/success")
@role_required("participant")
def payment_success(registration_id):
    reg = _get_own_registration(registration_id)
    payment_row = fetch_one(
        """SELECT * FROM payments WHERE registration_id = %s
           ORDER BY transaction_date DESC LIMIT 1""",
        (registration_id,),
    )
    if not payment_row:
        flash("No payment found for this registration.", "warning")
        return redirect(url_for("participant.payment", registration_id=registration_id))

    event = {"title": reg["event_title"]}
    return render_template(
        "payment_success.html",
        event=event,
        payment=payment_row,
        registration=reg,
    )


# ============================================================
#  FEEDBACK
# ============================================================
@participant_bp.route("/feedback/<int:registration_id>")
@role_required("participant")
def feedback(registration_id):
    reg = _get_own_registration(registration_id)

    if reg["attendance_status"] != "present":
        flash("Feedback is available after you've attended the event.", "warning")
        return redirect(url_for("participant.my_registrations"))

    event = {"title": reg["event_title"]}
    return render_template("feedback.html", event=event, registration=reg)


@participant_bp.route("/feedback/<int:registration_id>/submit", methods=["POST"])
@role_required("participant")
def submit_feedback(registration_id):
    reg = _get_own_registration(registration_id)

    rating = request.form.get("rating", "").strip()
    comments = request.form.get("comments", "").strip()

    if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
        flash("Please choose a star rating before submitting.", "danger")
        return redirect(url_for("participant.feedback", registration_id=registration_id))

    insert(
        """INSERT INTO feedback (registration_id, rating, comments)
           VALUES (%s, %s, %s)""",
        (registration_id, int(rating), comments),
    )
    execute(
        "UPDATE registrations SET feedback_given = 1 WHERE id = %s",
        (registration_id,),
    )

    flash("Thanks for your feedback! 🙌", "success")
    return redirect(url_for("participant.my_registrations"))


# ============================================================
#  CERTIFICATE
# ============================================================
@participant_bp.route("/certificate/<int:registration_id>")
@role_required("participant")
def certificate(registration_id):
    reg = _get_own_registration(registration_id)

    if reg["attendance_status"] != "present":
        flash("Certificates are issued after attendance is verified.", "warning")
        return redirect(url_for("participant.my_registrations"))
    if not reg["feedback_given"]:
        flash("Please submit feedback first to unlock your certificate.", "warning")
        return redirect(url_for("participant.feedback", registration_id=registration_id))

    if not reg["certificate_issued"]:
        execute(
            "UPDATE registrations SET certificate_issued = 1 WHERE id = %s",
            (registration_id,),
        )

    return render_template("certificate.html", registration=reg)