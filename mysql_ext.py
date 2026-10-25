"""
mysql_ext.py — Minimal drop-in replacement for Flask-MySQLdb.

Why this exists: Flask-MySQLdb 2.0.0 imports `flask._app_ctx_stack`,
which was removed from Flask years ago (you're on Flask 3.0.3). Its
underlying dependency, mysqlclient, also requires a C compiler to install
on Windows, which causes a separate class of headaches. PyMySQL is pure
Python and has none of these problems.

This class exposes the same `mysql.connection` property that the rest of
the codebase (db.py, app.py, organizer_routes.py) already expects, so
nothing else needs to change — just the import and initialization in
app.py.

One PyMySQL connection is opened per request (stored on flask.g) and
closed automatically when the request ends.
"""

import pymysql
import pymysql.cursors
from flask import current_app, g


class MySQL:
    def init_app(self, app):
        app.config.setdefault("MYSQL_HOST", "localhost")
        app.config.setdefault("MYSQL_USER", "root")
        app.config.setdefault("MYSQL_PASSWORD", "")
        app.config.setdefault("MYSQL_DB", "")
        app.config.setdefault("MYSQL_CURSORCLASS", "Cursor")

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["mysql"] = self

        @app.teardown_appcontext
        def _close_connection(exception=None):
            conn = g.pop("mysql_connection", None)
            if conn is not None:
                conn.close()

    @property
    def connection(self):
        """Returns a PyMySQL connection, opening one for this request if needed."""
        if "mysql_connection" not in g:
            cfg = current_app.config
            default_cursorclass = getattr(
                pymysql.cursors, cfg.get("MYSQL_CURSORCLASS", "Cursor"), pymysql.cursors.Cursor
            )
            g.mysql_connection = pymysql.connect(
                host=cfg["MYSQL_HOST"],
                user=cfg["MYSQL_USER"],
                password=cfg["MYSQL_PASSWORD"],
                database=cfg["MYSQL_DB"],
                cursorclass=default_cursorclass,
                autocommit=False,
                charset="utf8mb4",
            )
        return g.mysql_connection