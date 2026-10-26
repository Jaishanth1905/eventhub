import os
from app import create_app
from db import fetch_all
from utils import generate_qr_image
 
app = create_app()
base = os.getenv("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/")
with app.app_context():
    for r in fetch_all("SELECT ticket_code FROM registrations"):
        generate_qr_image(f"{base}/t/{r['ticket_code']}", r["ticket_code"])
        print("rebuilt", r["ticket_code"])