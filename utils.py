import os
import ipaddress
import secrets
import time as time_module
from datetime import time
from urllib.parse import urlsplit
 
import qrcode
from flask import current_app, has_request_context
 
 
def generate_ticket_code():
    """Unique, human-readable ticket code stored in registrations.ticket_code."""
    return "EH-" + secrets.token_hex(5).upper()
 
 
def public_ticket_url(ticket_code):
    """URL a phone opens after scanning the ticket QR."""
    from flask import request

    fallback = request.host_url if has_request_context() else None
    return f"{get_public_base_url(fallback)}/t/{ticket_code}"


def get_public_base_url(fallback=None):
    """Return a configured phone-reachable URL, rejecting loopback addresses."""
    base = current_app.config["PUBLIC_BASE_URL"] or (fallback or "").strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(
            "Set PUBLIC_BASE_URL to the app's phone-reachable URL, "
            "for example http://192.168.1.10:5001."
        )

    hostname = parsed.hostname.lower()
    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname == "localhost" or hostname.endswith(".localhost")
    if is_loopback:
        raise ValueError(
            "The QR URL points to this device only. Set PUBLIC_BASE_URL in .env "
            "to the computer's LAN IP, for example http://192.168.1.10:5001."
        )
    return base
 
 
def generate_qr_image(data, name=None):
    """Generate a QR code PNG containing ⁠ data ⁠.
    Saves it in static/uploads/qr/<name or data>.png and returns the filename."""
    img = qrcode.make(data)
    filename = f"{name or data}.png"
    path = os.path.join(current_app.config["QR_FOLDER"], filename)
    img.save(path)
    return filename
 
 
def generate_payment_id():
    """Fake sandbox payment reference ID."""
    return "PAY" + str(int(time_module.time() * 1000)) + secrets.token_hex(3).upper()
 
 
def timedelta_to_time(td):
    """
    PyMySQL returns MySQL TIME columns as datetime.timedelta (not
    datetime.time, which is what MySQLdb used to return) -- because TIME
    in MySQL can technically exceed 24 hours. Our event_sessions.start_time
    and end_time are always well within a single day, so this converts
    back to a normal time object that templates can call .strftime() on.
 
    Returns None if td is None (e.g. a NULL column).
    """
    if td is None:
        return None
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return time(hour=hours % 24, minute=minutes, second=seconds)