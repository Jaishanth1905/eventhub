"""
db.py — MySQL helper functions.

Usage:
    from db import fetch_one, fetch_all, execute, insert

    row  = fetch_one("SELECT * FROM users WHERE email = %s", (email,))
    rows = fetch_all("SELECT * FROM events WHERE approval_state = 'approved'")
    execute("UPDATE events SET approval_state = %s WHERE id = %s", ("approved", 5))
    new_id = insert("INSERT INTO users (...) VALUES (...)", (...))

Uses the PyMySQL-based connection from mysql_ext.py (see that file for why
Flask-MySQLdb was replaced). fetch_one/fetch_all explicitly request
pymysql.cursors.DictCursor on every call so rows always come back as dicts.
"""

import pymysql.cursors
from flask import current_app


def _connection():
    """Get the PyMySQL connection from the mysql_ext extension."""
    return current_app.extensions["mysql"].connection


def fetch_one(query, params=()):
    """Return one row as a dict, or None."""
    cur = _connection().cursor(pymysql.cursors.DictCursor)
    try:
        cur.execute(query, params)
        return cur.fetchone()
    finally:
        cur.close()


def fetch_all(query, params=()):
    """Return all rows as a list of dicts."""
    cur = _connection().cursor(pymysql.cursors.DictCursor)
    try:
        cur.execute(query, params)
        return cur.fetchall()
    finally:
        cur.close()


def execute(query, params=()):
    """Run INSERT/UPDATE/DELETE. Commits automatically. Returns affected rows."""
    cur = _connection().cursor()
    try:
        cur.execute(query, params)
        _connection().commit()
        return cur.rowcount
    finally:
        cur.close()


def insert(query, params=()):
    """Run INSERT and return the new row's auto-increment id."""
    cur = _connection().cursor()
    try:
        cur.execute(query, params)
        _connection().commit()
        return cur.lastrowid
    finally:
        cur.close()