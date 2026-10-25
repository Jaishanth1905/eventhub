import os
from datetime import datetime, timedelta

import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", ""),
    database=os.getenv("MYSQL_DB", "eventhub"),
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=False,
    charset="utf8mb4",
)


def get_or_create_organizer():
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", ("dhrona@gmail.com",))
        row = cur.fetchone()
        if row:
            print(f"[=] Organizer 'dhrona@gmail.com' already exists (id={row['id']}).")
            return row["id"]

        cur.execute(
            """INSERT INTO users (name, email, phone, password_hash, role)
               VALUES (%s, %s, %s, %s, 'organizer')""",
            (
                "Dhrona",
                "dhrona@gmail.com",
                "1234567890",
                generate_password_hash("123456"),
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
        print(f"[✔] Created organizer 'dhrona@gmail.com' (id={new_id}).")
        return new_id


def event_exists(title):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM events WHERE title = %s", (title,))
        return cur.fetchone()


def create_event(organizer_id, title, category, description, venue, days_from_now,
                  hour, capacity, fee_type, fee, deadline_days_from_now):
    existing = event_exists(title)
    if existing:
        print(f"[=] Event '{title}' already exists (id={existing['id']}). Skipping.")
        return existing["id"]

    start_dt = (datetime.now() + timedelta(days=days_from_now)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    deadline = (datetime.now() + timedelta(days=deadline_days_from_now)).date()

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events
                (organizer_id, title, category, description, venue, poster,
                 start_datetime, registration_deadline, capacity,
                 fee_type, fee, approval_state, submitted_at)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, 'approved', %s)
            """,
            (
                organizer_id, title, category, description, venue,
                start_dt, deadline, capacity, fee_type, fee, datetime.now(),
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
        print(f"[✔] Created event '{title}' (id={new_id}) on {start_dt.strftime('%d %b %Y')}.")
        return new_id


def add_session(event_id, session_name, speaker, session_date, start_time, end_time, venue):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM event_sessions WHERE event_id = %s AND session_name = %s",
            (event_id, session_name),
        )
        if cur.fetchone():
            return
        cur.execute(
            """INSERT INTO event_sessions
                   (event_id, session_name, speaker, session_date, start_time, end_time, venue)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (event_id, session_name, speaker, session_date, start_time, end_time, venue),
        )
        conn.commit()


def main():
    organizer_id = get_or_create_organizer()

    events = [
        dict(
            title="AI & Machine Learning Workshop",
            category="Workshop",
            description="A hands-on introduction to machine learning fundamentals, "
                         "covering supervised learning, neural networks, and a live "
                         "coding session building your first model.",
            venue="Auditorium A",
            days_from_now=7, hour=10, capacity=120,
            fee_type="free", fee=0, deadline_days_from_now=5,
        ),
        dict(
            title="National Coding Hackathon 2026",
            category="Hackathon",
            description="24-hour hackathon where teams build and pitch a working "
                         "prototype. Mentors on-site, prizes for top 3 teams, and "
                         "free meals throughout.",
            venue="Open Air Theatre",
            days_from_now=14, hour=9, capacity=200,
            fee_type="paid", fee=499, deadline_days_from_now=10,
        ),
        dict(
            title="Entrepreneurship & Startup Summit",
            category="Seminar",
            description="Founders and investors share insights on building and "
                         "scaling a startup, followed by a networking session and "
                         "a pitch competition.",
            venue="Seminar Hall B",
            days_from_now=10, hour=11, capacity=150,
            fee_type="paid", fee=299, deadline_days_from_now=7,
        ),
        dict(
            title="Cultural Fest — Rhythms 2026",
            category="Cultural",
            description="An evening of music, dance, and drama performances from "
                         "student clubs, capped off with a live band performance.",
            venue="Open Air Theatre",
            days_from_now=21, hour=17, capacity=500,
            fee_type="free", fee=0, deadline_days_from_now=18,
        ),
        dict(
            title="Inter-College Basketball Championship",
            category="Sports",
            description="Knockout basketball tournament between college teams from "
                         "across the region, finals streamed live.",
            venue="Sports Complex",
            days_from_now=18, hour=15, capacity=300,
            fee_type="free", fee=0, deadline_days_from_now=15,
        ),
        dict(
            title="Web Development Bootcamp",
            category="Workshop",
            description="Three-hour intensive on modern web development — HTML, "
                         "CSS, JavaScript, and deploying your first live site.",
            venue="Seminar Hall B",
            days_from_now=5, hour=14, capacity=80,
            fee_type="free", fee=0, deadline_days_from_now=3,
        ),
        dict(
            title="Photography Walk & Exhibition",
            category="Cultural",
            description="A guided photography walk across campus followed by an "
                         "exhibition of the best shots, with prizes for top entries.",
            venue="Campus Grounds",
            days_from_now=12, hour=8, capacity=60,
            fee_type="paid", fee=99, deadline_days_from_now=9,
        ),
        dict(
            title="Tech Symposium — Future of Computing",
            category="Seminar",
            description="Industry speakers cover trends in cloud computing, AI, "
                         "and cybersecurity, with a Q&A panel to close.",
            venue="Auditorium A",
            days_from_now=25, hour=10, capacity=180,
            fee_type="paid", fee=199, deadline_days_from_now=20,
        ),
        dict(
            title="Robotics Design Challenge",
            category="Workshop",
            description="Teams design and build a small robot to complete an "
                         "obstacle course, with kits provided on-site.",
            venue="Seminar Hall B",
            days_from_now=16, hour=9, capacity=100,
            fee_type="paid", fee=349, deadline_days_from_now=12,
        ),
    ]

    event_ids = {}
    for e in events:
        eid = create_event(organizer_id, **e)
        event_ids[e["title"]] = eid

    # A couple of sample sessions, so the schedule section has content to show
    hackathon_id = event_ids.get("National Coding Hackathon 2026")
    if hackathon_id:
        start_date = (datetime.now() + timedelta(days=14)).date()
        add_session(hackathon_id, "Opening Ceremony & Team Briefing", "Dhrona",
                    start_date, "09:00:00", "10:00:00", "Open Air Theatre")
        add_session(hackathon_id, "Hacking Begins", "—",
                    start_date, "10:00:00", "18:00:00", "Open Air Theatre")
        add_session(hackathon_id, "Final Pitches & Judging", "Panel of Judges",
                    (datetime.now() + timedelta(days=15)).date(), "09:00:00", "12:00:00",
                    "Open Air Theatre")

    ai_workshop_id = event_ids.get("AI & Machine Learning Workshop")
    if ai_workshop_id:
        start_date = (datetime.now() + timedelta(days=7)).date()
        add_session(ai_workshop_id, "Intro to Machine Learning", "Dhrona",
                    start_date, "10:00:00", "11:30:00", "Auditorium A")
        add_session(ai_workshop_id, "Hands-on: Building Your First Model", "Dhrona",
                    start_date, "11:45:00", "13:00:00", "Auditorium A")

    print("\nDone! Log in as the organizer to view/manage these events:")
    print("  Email:    dhrona@gmail.com")
    print("  Password: 123456")


if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()