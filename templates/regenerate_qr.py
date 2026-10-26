from app import create_app
from db import fetch_all
from utils import generate_qr_image, get_public_base_url
 
app = create_app()
with app.app_context():
    base = get_public_base_url()
    for r in fetch_all("SELECT ticket_code FROM registrations"):
        generate_qr_image(f"{base}/t/{r['ticket_code']}", r["ticket_code"])
        print("rebuilt", r["ticket_code"])