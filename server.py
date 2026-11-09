"""Small, self-hosted stock system prototype (Python standard library only)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import socket
import time
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DATA = ROOT / "data"
DB_PATH = DATA / "inventory.sqlite3"
HOST = os.environ.get("STOCK_HOST", "0.0.0.0")
PORT = int(os.environ.get("STOCK_PORT", "8080"))
SESSION_SECONDS = 60 * 60 * 24 * 14


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def lan_ipv4_addresses() -> list[str]:
    addresses = set()
    # Ask Windows which IPv4 interface it would use for an outbound route.
    # UDP connect selects the route without sending a packet to the destination.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.0.2.1", 80))
        address = probe.getsockname()[0]
        probe.close()
        if address and not address.startswith(("127.", "169.254.")):
            addresses.add(address)
    except OSError:
        pass
    try:
        _, _, ip_list = socket.gethostbyname_ex(socket.gethostname())
        for address in ip_list:
            if address and not address.startswith(("127.", "169.254.")):
                addresses.add(address)
    except OSError:
        pass
    if not addresses:
        try:
            for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                address = result[4][0]
                if address and not address.startswith(("127.", "169.254.")):
                    addresses.add(address)
        except OSError:
            pass
    return sorted(addresses)


def db() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('stock','employee')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT NOT NULL,
            parent_id INTEGER REFERENCES locations(id),
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            item_code TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Uncategorized',
            part_number TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'consumable' CHECK(kind IN ('consumable','asset')),
            unit TEXT NOT NULL DEFAULT 'Nos',
            min_qty INTEGER,
            needs_count INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stock (
            item_id INTEGER NOT NULL REFERENCES items(id),
            location_id INTEGER NOT NULL REFERENCES locations(id),
            quantity INTEGER NOT NULL DEFAULT 0,
            needs_count INTEGER NOT NULL DEFAULT 0,
            reference_quantity INTEGER,
            PRIMARY KEY(item_id, location_id)
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            ref TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            item_id INTEGER NOT NULL REFERENCES items(id),
            location_id INTEGER NOT NULL REFERENCES locations(id),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            user_id INTEGER NOT NULL REFERENCES users(id),
            project_id INTEGER REFERENCES projects(id),
            purpose TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('pending','confirmed','rejected')),
            condition_note TEXT NOT NULL DEFAULT '',
            related_request_id INTEGER,
            created_at TEXT NOT NULL,
            confirmed_by INTEGER REFERENCES users(id),
            confirmed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES items(id),
            location_id INTEGER NOT NULL REFERENCES locations(id),
            borrower_id INTEGER NOT NULL REFERENCES users(id),
            project_id INTEGER REFERENCES projects(id),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            status TEXT NOT NULL CHECK(status IN ('issued','return_pending','returned')),
            issued_at TEXT NOT NULL,
            returned_at TEXT,
            condition_note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS stock_counts (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES items(id),
            location_id INTEGER NOT NULL REFERENCES locations(id),
            previous_quantity INTEGER NOT NULL,
            counted_quantity INTEGER NOT NULL,
            counted_by INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS purchase_requests (
            id INTEGER PRIMARY KEY,
            ref TEXT NOT NULL UNIQUE,
            requester_id INTEGER NOT NULL REFERENCES users(id),
            project_id INTEGER REFERENCES projects(id),
            purpose TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','ordered','partially_received','received')),
            decision_by INTEGER REFERENCES users(id),
            decision_at TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS request_lines (
            id INTEGER PRIMARY KEY,
            request_id INTEGER NOT NULL REFERENCES purchase_requests(id) ON DELETE CASCADE,
            item_id INTEGER REFERENCES items(id),
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            received_quantity INTEGER NOT NULL DEFAULT 0,
            vendor TEXT NOT NULL DEFAULT '',
            product_url TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_requests_status ON purchase_requests(status, created_at DESC);
        """)
        stock_columns = {r[1] for r in c.execute("PRAGMA table_info(stock)")}
        if "needs_count" not in stock_columns:
            c.execute("ALTER TABLE stock ADD COLUMN needs_count INTEGER NOT NULL DEFAULT 0")
        if "reference_quantity" not in stock_columns:
            c.execute("ALTER TABLE stock ADD COLUMN reference_quantity INTEGER")
        transaction_columns = {r[1] for r in c.execute("PRAGMA table_info(transactions)")}
        if "issued_to_id" not in transaction_columns:
            c.execute("ALTER TABLE transactions ADD COLUMN issued_to_id INTEGER REFERENCES users(id)")
        request_line_columns = {r[1] for r in c.execute("PRAGMA table_info(request_lines)")}
        if "vendor" not in request_line_columns:
            c.execute("ALTER TABLE request_lines ADD COLUMN vendor TEXT NOT NULL DEFAULT ''")
        if "product_url" not in request_line_columns:
            c.execute("ALTER TABLE request_lines ADD COLUMN product_url TEXT NOT NULL DEFAULT ''")
        loan_columns = {r[1] for r in c.execute("PRAGMA table_info(loans)")}
        if "remaining_qty" not in loan_columns:
            c.execute("ALTER TABLE loans ADD COLUMN remaining_qty INTEGER")
            c.execute("UPDATE loans SET remaining_qty = CASE WHEN status='returned' THEN 0 ELSE quantity END")
        if "consumed_qty" not in loan_columns:
            c.execute("ALTER TABLE loans ADD COLUMN consumed_qty INTEGER NOT NULL DEFAULT 0")


def password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 240_000).hex()


def user_dict(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"]}


class APIError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message, self.status = message, status


class Handler(BaseHTTPRequestHandler):
    server_version = "StockDesk/0.1"

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_json(self, obj, status=200):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise APIError("Request is too large", 413)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise APIError("Invalid JSON")

    def cookie_token(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("stock_session")
        return morsel.value if morsel else ""

    def current_user(self, required=True):
        token = self.cookie_token()
        if token:
            with db() as c:
                row = c.execute("""SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                    WHERE s.token=? AND s.expires_at>? AND u.active=1""", (token, int(time.time()))).fetchone()
            if row:
                return row
        if required:
            raise APIError("Please sign in", 401)
        return None

    def require_stock(self):
        u = self.current_user()
        if u["role"] != "stock":
            raise APIError("Only the stock person can do this", 403)
        return u

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/"):
                self.api_get(path)
            else:
                self.static_file(path)
        except APIError as e:
            self.send_json({"error": e.message}, e.status)
        except Exception as e:
            print("API error:", repr(e))
            self.send_json({"error": "Something went wrong. Please try again."}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self.body()
            self.api_post(path, data)
        except APIError as e:
            self.send_json({"error": e.message}, e.status)
        except sqlite3.IntegrityError as e:
            print("Integrity error:", repr(e))
            self.send_json({"error": "That record already exists or is in use."}, 409)
        except Exception as e:
            print("API error:", repr(e))
            self.send_json({"error": "Something went wrong. Please try again."}, 500)

    def do_DELETE(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/users/"):
                u = self.require_stock()
                user_id = int(path.rsplit("/", 1)[1])
                if user_id == u["id"]:
                    raise APIError("You cannot deactivate your own account")
                with db() as c:
                    c.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
                self.send_json({"ok": True})
            elif path.startswith("/api/requests/"):
                u = self.require_stock()
                req_id = int(path.rsplit("/", 1)[1])
                res = self.delete_request(req_id, u)
                self.send_json(res or {"ok": True})
            else:
                raise APIError("Not found", 404)
        except APIError as e:
            self.send_json({"error": e.message}, e.status)

    def static_file(self, path):
        if path in ("/", ""):
            path = "/index.html"
        target = (STATIC / unquote(path.lstrip("/"))).resolve()
        if STATIC.resolve() not in target.parents and target != STATIC.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        content_type = "text/plain; charset=utf-8"
        if target.suffix == ".html": content_type = "text/html; charset=utf-8"
        elif target.suffix == ".css": content_type = "text/css; charset=utf-8"
        elif target.suffix == ".js": content_type = "text/javascript; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def api_get(self, path):
        if path == "/api/network-info":
            addresses = lan_ipv4_addresses()
            self.send_json({
                "port": PORT,
                "local_url": f"http://127.0.0.1:{PORT}/",
                "wifi_urls": [f"http://{addr}:{PORT}/" for addr in addresses],
                "primary_wifi_url": f"http://{addresses[0]}:{PORT}/" if addresses else None
            })
            return
        if path == "/api/setup-status":
            with db() as c:
                count = c.execute("SELECT count(*) FROM users WHERE active=1").fetchone()[0]
            self.send_json({"setup_required": count == 0})
            return
        if path == "/api/me":
            u = self.current_user(False)
            self.send_json({"user": user_dict(u) if u else None})
            return
        u = self.current_user()
        if path == "/api/bootstrap":
            with db() as c:
                self.send_json({"user": user_dict(u), "data": self.bootstrap_data(c, u)})
            return
        if path == "/api/export.csv":
            self.export_csv(u)
            return
        raise APIError("Not found", 404)

    def bootstrap_data(self, c, u):
        raw_locations = [dict(r) for r in c.execute("SELECT * FROM locations WHERE active=1")]
        by_location = {r["id"]: r for r in raw_locations}
        path_cache = {}
        def location_path(location_id):
            if location_id in path_cache: return path_cache[location_id]
            row = by_location.get(location_id)
            if not row: return "Unknown location"
            prefix = location_path(row["parent_id"]) if row["parent_id"] in by_location else ""
            path_cache[location_id] = f"{prefix} / {row['name']}" if prefix else row["name"]
            return path_cache[location_id]
        def get_high_rack(path):
            parts = [p.strip() for p in (path or "").split(" / ")]
            if len(parts) > 1 and "stock room" in parts[0].lower():
                return parts[1]
            return parts[0] if parts and parts[0] else "No location"
        for loc in raw_locations:
            loc["path"] = location_path(loc["id"])
            loc["high_rack"] = get_high_rack(loc["path"])
            loc["is_root"] = loc["parent_id"] is None
            loc["is_leaf"] = not any(child["parent_id"] == loc["id"] for child in raw_locations)
        items = c.execute("""SELECT i.*, COALESCE(SUM(s.quantity),0) AS total_qty,
            COALESCE(SUM(CASE WHEN i.min_qty IS NOT NULL AND s.quantity>0 THEN s.quantity ELSE 0 END),0) AS _x
            FROM items i LEFT JOIN stock s ON s.item_id=i.id WHERE i.active=1 GROUP BY i.id ORDER BY i.name COLLATE NOCASE""").fetchall()
        stock_rows = c.execute("""SELECT i.id AS item_id,l.id AS location_id,l.code,l.name,st.quantity,st.needs_count,st.reference_quantity
            FROM stock st JOIN items i ON i.id=st.item_id JOIN locations l ON l.id=st.location_id
            WHERE i.active=1 ORDER BY l.code,i.name""").fetchall()
        locmap = {}
        for r in stock_rows:
            p = location_path(r["location_id"])
            locmap.setdefault(r["item_id"], []).append({"id": r["location_id"], "code": r["code"], "name": r["name"], "path": p, "high_rack": get_high_rack(p), "quantity": r["quantity"], "needs_count": bool(r["needs_count"]), "reference_quantity": r["reference_quantity"]})
        item_list = []
        for r in items:
            d = dict(r)
            d["locations"] = locmap.get(r["id"], [])
            d["high_racks"] = sorted(list(set(l["high_rack"] for l in d["locations"] if l.get("high_rack"))))
            d["low_stock"] = r["min_qty"] is not None and r["total_qty"] <= r["min_qty"]
            item_list.append(d)
        overview = {
            "item_count": c.execute("SELECT count(*) FROM items WHERE active=1").fetchone()[0],
            "units": c.execute("SELECT COALESCE(SUM(quantity),0) FROM stock").fetchone()[0],
            "low_stock": sum(1 for i in item_list if i["low_stock"]),
            "out_of_stock": sum(1 for i in item_list if i["total_qty"] == 0 and not i["needs_count"]),
            "needs_count": sum(1 for i in item_list if i["needs_count"]),
            "pending_transactions": c.execute("SELECT count(*) FROM transactions WHERE status='pending'").fetchone()[0],
            "open_requests": c.execute("SELECT count(*) FROM purchase_requests WHERE status IN ('pending','approved','ordered','partially_received')").fetchone()[0],
            "my_loans": c.execute("SELECT count(*) FROM loans WHERE borrower_id=? AND status NOT IN ('returned','closed') AND COALESCE(remaining_qty, quantity)>0", (u["id"],)).fetchone()[0],
            "staff_loans": c.execute("SELECT count(*) FROM loans WHERE status NOT IN ('returned','closed') AND COALESCE(remaining_qty, quantity)>0").fetchone()[0],
            "my_open_requests": c.execute("SELECT count(*) FROM purchase_requests WHERE requester_id=? AND status IN ('pending','approved','ordered','partially_received')", (u["id"],)).fetchone()[0],
            "my_items_taken": c.execute("SELECT COALESCE(SUM(quantity),0) FROM transactions WHERE (user_id=? OR issued_to_id=?) AND kind='issue' AND status='confirmed'", (u["id"], u["id"])).fetchone()[0],
            "my_pending_actions": c.execute("SELECT count(*) FROM transactions WHERE user_id=? AND status='pending'", (u["id"],)).fetchone()[0],
        }
        tx = c.execute("""SELECT t.*,i.name AS item_name,l.code AS location_code,u.name AS user_name,
            issued_to.name AS issued_to_name,
            p.name AS project_name FROM transactions t JOIN items i ON i.id=t.item_id
            JOIN locations l ON l.id=t.location_id JOIN users u ON u.id=t.user_id
            LEFT JOIN users issued_to ON issued_to.id=t.issued_to_id
            LEFT JOIN projects p ON p.id=t.project_id ORDER BY t.id DESC""").fetchall()
        requests = c.execute("""SELECT r.*,u.name AS requester,p.name AS project_name,
            (SELECT group_concat(item_name, ', ') FROM request_lines WHERE request_id=r.id) AS item_summary
            FROM purchase_requests r JOIN users u ON u.id=r.requester_id
            LEFT JOIN projects p ON p.id=r.project_id ORDER BY r.id DESC LIMIT 30""").fetchall()
        lines = c.execute("SELECT * FROM request_lines ORDER BY id").fetchall()
        req_lines = {}
        for line in lines:
            req_lines.setdefault(line["request_id"], []).append(dict(line))
        raw_locations.sort(key=lambda loc: loc["path"].casefold())
        projects = [dict(r) for r in c.execute("SELECT * FROM projects WHERE active=1 ORDER BY name")]
        users = [user_dict(r) for r in c.execute("SELECT * FROM users WHERE active=1 ORDER BY name")]
        all_loans = c.execute("""SELECT l.*, COALESCE(l.remaining_qty, l.quantity) AS remaining_qty,
            COALESCE(l.consumed_qty, 0) AS consumed_qty,
            i.name AS item_name, i.item_code, i.category, i.unit, loc.code AS location_code, u.name AS borrower, p.name AS project_name
            FROM loans l JOIN items i ON i.id=l.item_id JOIN locations loc ON loc.id=l.location_id
            JOIN users u ON u.id=l.borrower_id LEFT JOIN projects p ON p.id=l.project_id
            ORDER BY l.id DESC LIMIT 150""").fetchall()
        tx_list = [dict(r) for r in tx]
        for movement in tx_list: movement["location_path"] = location_path(movement["location_id"])
        all_loan_list = [dict(r) for r in all_loans]
        for loan in all_loan_list: loan["location_path"] = location_path(loan["location_id"])
        loan_list = [l for l in all_loan_list if l["status"] not in ('returned','closed') and l["remaining_qty"] > 0]
        return {"overview": overview, "items": item_list, "transactions": tx_list,
                "requests": [{**dict(r), "lines": req_lines.get(r["id"], [])} for r in requests],
                "locations": raw_locations, "projects": projects, "users": users, "loans": loan_list, "checkouts": all_loan_list}

    def api_post(self, path, d):
        if path == "/api/setup":
            with db() as c:
                if c.execute("SELECT count(*) FROM users WHERE active=1").fetchone()[0]:
                    raise APIError("Initial setup is already complete", 409)
                name, email, password = self.validate_user(d)
                salt = secrets.token_hex(16)
                cur = c.execute("INSERT INTO users(email,name,password_hash,salt,role,created_at) VALUES(?,?,?,?,?,?)",
                                (email, name, password_hash(password, salt), salt, "stock", now()))
                token = self.create_session(cur.lastrowid, c)
            self.send_auth_success(token)
            return
        if path == "/api/login":
            email, password = str(d.get("email", "")).strip(), str(d.get("password", ""))
            with db() as c:
                row = c.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE AND active=1", (email,)).fetchone()
                if not row or not hmac.compare_digest(password_hash(password, row["salt"]), row["password_hash"]):
                    raise APIError("Email or password is incorrect", 401)
                token = self.create_session(row["id"], c)
            self.send_auth_success(token)
            return
        if path == "/api/logout":
            token = self.cookie_token()
            with db() as c: c.execute("DELETE FROM sessions WHERE token=?", (token,))
            self.send_response(200)
            self.send_header("Set-Cookie", "stock_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
            return
        if path == "/api/users":
            self.require_stock()
            name, email, password = self.validate_user(d)
            role = d.get("role", "employee")
            if role not in ("stock", "employee"): raise APIError("Choose employee or stock person")
            salt = secrets.token_hex(16)
            with db() as c:
                c.execute("INSERT INTO users(email,name,password_hash,salt,role,created_at) VALUES(?,?,?,?,?,?)",
                          (email,name,password_hash(password,salt),salt,role,now()))
            self.send_json({"ok": True}, 201)
            return
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "users" and parts[3] == "edit":
            currentUser = self.require_stock()
            user_id = self.integer(parts[2], "User ID")
            name = str(d.get("name", "")).strip()
            email = str(d.get("email", "")).strip().lower()
            role = str(d.get("role", "employee")).strip()
            password = str(d.get("password", "")).strip()
            if not name or "@" not in email:
                raise APIError("Enter a valid name and company email")
            if role not in ("stock", "employee"):
                raise APIError("Choose employee or stock person")
            if user_id == currentUser["id"] and role != "stock":
                with db() as c:
                    stock_count = c.execute("SELECT count(*) FROM users WHERE role='stock' AND active=1 AND id!=?", (user_id,)).fetchone()[0]
                if stock_count == 0:
                    raise APIError("At least one active stock person account is required")
            with db() as c:
                existing = c.execute("SELECT id FROM users WHERE email=? AND id!=?", (email, user_id)).fetchone()
                if existing:
                    raise APIError("A user with that email already exists")
                if password:
                    if len(password) < 8:
                        raise APIError("Password must be at least 8 characters")
                    salt = secrets.token_hex(16)
                    c.execute("UPDATE users SET name=?, email=?, role=?, password_hash=?, salt=? WHERE id=?",
                              (name, email, role, password_hash(password, salt), salt, user_id))
                else:
                    c.execute("UPDATE users SET name=?, email=?, role=? WHERE id=?",
                              (name, email, role, user_id))
            self.send_json({"ok": True})
            return
        u = self.current_user()
        if path == "/api/items":
            self.require_stock()
            self.create_item(d, u["id"])
            self.send_json({"ok": True}, 201)
            return
        if path.startswith("/api/items/") and path.endswith("/count"):
            self.count_stock(int(path.split("/")[3]), d, u)
            self.send_json({"ok": True})
            return
        if path.startswith("/api/items/") and path.endswith("/edit"):
            self.update_item(int(path.split("/")[3]), d, u)
            self.send_json({"ok": True})
            return
        if path == "/api/locations":
            self.require_stock()
            name = str(d.get("name", "")).strip()
            parent_id = d.get("parent_id")
            if not name: raise APIError("Enter a location name")
            with db() as c:
                if parent_id:
                    parent = c.execute("SELECT id FROM locations WHERE id=? AND active=1", (int(parent_id),)).fetchone()
                    if not parent: raise APIError("Choose a valid parent location")
                else:
                    parent = c.execute("SELECT id FROM locations WHERE code='STOCK-ROOM'").fetchone()
                    if parent: parent_id = parent["id"]
                import re
                slug = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:32] or "LOCATION"
                code = f"LOC-{slug}-{secrets.token_hex(3).upper()}"
                c.execute("INSERT INTO locations(code,name,parent_id) VALUES(?,?,?)", (code,name,parent_id))
            self.send_json({"ok": True}, 201)
            return
        if path == "/api/projects":
            self.require_stock()
            name = str(d.get("name", "")).strip()
            if not name: raise APIError("Enter a project name")
            with db() as c: c.execute("INSERT INTO projects(name) VALUES(?)", (name,))
            self.send_json({"ok": True}, 201)
            return
        if path == "/api/transactions":
            self.create_transaction(d, u)
            self.send_json({"ok": True}, 201)
            return
        if path.startswith("/api/transactions/") and path.endswith("/confirm"):
            self.confirm_transaction(int(path.split("/")[3]), u)
            self.send_json({"ok": True})
            return
        if path.startswith("/api/transactions/") and path.endswith("/reject"):
            self.reject_transaction(int(path.split("/")[3]), u)
            self.send_json({"ok": True})
            return
        if path == "/api/requests":
            self.create_request(d, u)
            self.send_json({"ok": True}, 201)
            return
        if path.startswith("/api/requests/") and path.endswith("/status"):
            self.set_request_status(int(path.split("/")[3]), str(d.get("status", "")), u)
            self.send_json({"ok": True})
            return
        if path.startswith("/api/requests/") and path.endswith("/delete"):
            res = self.delete_request(int(path.split("/")[3]), u)
            self.send_json(res or {"ok": True})
            return
        if path.startswith("/api/requests/") and path.endswith("/receive"):
            self.receive_request_line(int(path.split("/")[3]), d, u)
            self.send_json({"ok": True})
            return
        if path.startswith("/api/loans/") and path.endswith("/return"):
            self.request_return(int(path.split("/")[3]), d, u)
            self.send_json({"ok": True}, 201)
            return
        if path.startswith("/api/loans/") and path.endswith("/consume"):
            self.consume_loan(int(path.split("/")[3]), d, u)
            self.send_json({"ok": True})
            return
        if path.startswith("/api/loans/") and path.endswith("/clear"):
            res = self.clear_loan(int(path.split("/")[3]), u)
            self.send_json(res or {"ok": True})
            return
        raise APIError("Not found", 404)

    def create_session(self, user_id, conn=None):
        token = secrets.token_urlsafe(32)
        if conn is None:
            with db() as c: c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token,user_id,int(time.time())+SESSION_SECONDS))
        else:
            conn.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token,user_id,int(time.time())+SESSION_SECONDS))
        return token

    def send_auth_success(self, token):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", f"stock_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_SECONDS}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def validate_user(self, d):
        name = str(d.get("name", "")).strip()
        email = str(d.get("email", "")).strip().lower()
        password = str(d.get("password", ""))
        if not name or "@" not in email: raise APIError("Enter a name and a valid email")
        if len(password) < 8: raise APIError("Password must be at least 8 characters")
        return name, email, password

    def create_item(self, d, user_id):
        name = str(d.get("name", "")).strip()
        code = str(d.get("item_code", "")).strip() or f"ITM-{secrets.token_hex(4).upper()}"
        category = str(d.get("category", "Uncategorized")).strip() or "Uncategorized"
        kind = d.get("kind", "consumable")
        if not name: raise APIError("Enter an item name")
        if kind not in ("consumable", "asset"): raise APIError("Choose consumable or reusable asset")
        minimum = d.get("min_qty")
        if minimum in ("", None): minimum = None
        else: minimum = self.integer(minimum, "Minimum quantity", allow_zero=True)
        initial = self.integer(d.get("quantity", 0), "Quantity", allow_zero=True)
        location_id = d.get("location_id")
        if initial and not location_id:
            raise APIError("Choose a storage location for the opening quantity")
        with db() as c:
            cur = c.execute("""INSERT INTO items(item_code,name,category,part_number,kind,unit,min_qty,needs_count,notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (code,name,category,str(d.get("part_number", "")).strip(),kind,"Nos",minimum,
                int(bool(d.get("needs_count", False))),str(d.get("notes", "")).strip(),now()))
            item_id = cur.lastrowid
            if initial and location_id:
                c.execute("INSERT INTO stock(item_id,location_id,quantity) VALUES(?,?,?)", (item_id,int(location_id),initial))
                c.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,status,purpose,created_at)
                    VALUES(?,?,?,?,?,?,'confirmed','Opening balance',?)""", (self.ref("TX"),"opening",item_id,int(location_id),initial,user_id,now()))

    def create_transaction(self, d, user):
        kind = d.get("kind")
        item_id, location_id = self.integer(d.get("item_id"),"Item"), self.integer(d.get("location_id"),"Location")
        qty = self.integer(d.get("quantity"),"Quantity")
        project_id = d.get("project_id") or None
        if project_id is not None: project_id = self.integer(project_id,"Project")
        purpose = str(d.get("purpose", "")).strip()
        if kind not in ("issue","inward"): raise APIError("Choose issue or inward")
        with db() as c:
            valid_location = c.execute("SELECT id FROM locations l WHERE id=? AND active=1 AND NOT EXISTS(SELECT 1 FROM locations child WHERE child.parent_id=l.id)", (location_id,)).fetchone()
            if not valid_location: raise APIError("Choose an active storage location")
            item = c.execute("SELECT * FROM items WHERE id=? AND active=1",(item_id,)).fetchone()
            if not item: raise APIError("Item not found",404)
            if kind == "issue":
                is_stock_person = (user["role"] == "stock")
                issue_type = str(d.get("issue_type", "already_taken" if not is_stock_person else "stock_issue")).strip()
                if is_stock_person:
                    issued_to_id = self.integer(d.get("issued_to_id", user["id"]), "Person receiving item")
                    recipient = c.execute("SELECT id FROM users WHERE id=? AND active=1", (issued_to_id,)).fetchone()
                    if not recipient: raise APIError("Choose an active employee to receive the item")
                else:
                    issued_to_id = user["id"]

                if issue_type == "kindly_issue":
                    # Employee requested stock person to issue/hand over item. Waits for stock person confirmation.
                    note = f"[Kindly issue] {purpose}".strip()
                    c.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,issued_to_id,project_id,purpose,status,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,'pending',?)""",(self.ref("TX"),"issue",item_id,location_id,qty,user["id"],issued_to_id,project_id,note,now()))
                else:
                    # 'already_taken' or stock person direct issue: deducts inventory immediately
                    if item["needs_count"]:
                        raise APIError("This item needs a physical count before it can be issued")
                    available = c.execute("SELECT quantity,needs_count FROM stock WHERE item_id=? AND location_id=?",(item_id,location_id)).fetchone()
                    current = available[0] if available else 0
                    if available and available["needs_count"]:
                        raise APIError("This location needs a physical count before it can be issued")
                    if qty > current: raise APIError(f"Only {current} available at this location. Submit a purchase request if more is needed.")
                    changed = c.execute("UPDATE stock SET quantity=quantity-? WHERE item_id=? AND location_id=? AND quantity>=? AND needs_count=0",(qty,item_id,location_id,qty))
                    if changed.rowcount != 1: raise APIError("Stock changed while this issue was being recorded. Refresh and try again.",409)
                    note = f"[Already taken] {purpose}".strip() if not is_stock_person else purpose
                    cur_tx = c.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,issued_to_id,project_id,purpose,status,created_at,confirmed_by,confirmed_at)
                        VALUES(?,?,?,?,?,?,?,?,?,'confirmed',?,?,?)""",(self.ref("TX"),"issue",item_id,location_id,qty,user["id"],issued_to_id,project_id,note,now(),user["id"],now()))
                    cur_loan = c.execute("""INSERT INTO loans(item_id,location_id,borrower_id,project_id,quantity,remaining_qty,consumed_qty,status,issued_at)
                        VALUES(?,?,?,?,?,?,0,'issued',?)""",(item_id,location_id,issued_to_id,project_id,qty,qty,now()))
                    c.execute("UPDATE transactions SET related_request_id=? WHERE id=?", (-cur_loan.lastrowid, cur_tx.lastrowid))
            else:
                c.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,purpose,status,created_at)
                    VALUES(?,?,?,?,?, ?,?,'pending',?)""",(self.ref("TX"),"inward",item_id,location_id,qty,user["id"],purpose,now()))

    def confirm_transaction(self, tx_id, user):
        self.require_stock()
        with db() as c:
            tx = c.execute("SELECT * FROM transactions WHERE id=? AND status='pending'",(tx_id,)).fetchone()
            if not tx: raise APIError("Pending transaction not found",404)
            if tx["kind"] == "inward":
                location = c.execute("SELECT id FROM locations l WHERE id=? AND active=1 AND NOT EXISTS(SELECT 1 FROM locations child WHERE child.parent_id=l.id)", (tx["location_id"],)).fetchone()
                if not location: raise APIError("The selected storage location is no longer available. Reject this entry and record it at a current location.")
                claimed = c.execute("UPDATE transactions SET status='confirmed',confirmed_by=?,confirmed_at=? WHERE id=? AND status='pending'", (user["id"],now(),tx_id))
                if claimed.rowcount != 1: raise APIError("This movement was already handled. Refresh the page.",409)
                c.execute("INSERT INTO stock(item_id,location_id,quantity) VALUES(?,?,?) ON CONFLICT(item_id,location_id) DO UPDATE SET quantity=quantity+excluded.quantity",
                          (tx["item_id"],tx["location_id"],tx["quantity"]))
            elif tx["kind"] == "issue":
                available = c.execute("SELECT quantity,needs_count FROM stock WHERE item_id=? AND location_id=?", (tx["item_id"], tx["location_id"])).fetchone()
                current = available[0] if available else 0
                if available and available["needs_count"]:
                    raise APIError("This location needs a physical count before this item can be issued")
                if tx["quantity"] > current:
                    raise APIError(f"Insufficient stock to confirm this issue (only {current} available).")
                changed = c.execute("UPDATE stock SET quantity=quantity-? WHERE item_id=? AND location_id=? AND quantity>=? AND needs_count=0",
                                    (tx["quantity"], tx["item_id"], tx["location_id"], tx["quantity"]))
                if changed.rowcount != 1:
                    raise APIError("Stock changed while confirming this issue. Refresh and try again.", 409)
                claimed = c.execute("UPDATE transactions SET status='confirmed',confirmed_by=?,confirmed_at=? WHERE id=? AND status='pending'", (user["id"],now(),tx_id))
                if claimed.rowcount != 1: raise APIError("This movement was already handled. Refresh the page.",409)
                recipient_id = tx["issued_to_id"] or tx["user_id"]
                cur_loan = c.execute("""INSERT INTO loans(item_id,location_id,borrower_id,project_id,quantity,remaining_qty,consumed_qty,status,issued_at)
                    VALUES(?,?,?,?,?,?,0,'issued',?)""",(tx["item_id"],tx["location_id"],recipient_id,tx["project_id"],tx["quantity"],tx["quantity"],now()))
                c.execute("UPDATE transactions SET related_request_id=? WHERE id=?", (-cur_loan.lastrowid, tx_id))
            elif tx["kind"] == "return":
                claimed = c.execute("UPDATE transactions SET status='confirmed',confirmed_by=?,confirmed_at=? WHERE id=? AND status='pending'", (user["id"],now(),tx_id))
                if claimed.rowcount != 1: raise APIError("This movement was already handled. Refresh the page.",409)
                c.execute("INSERT INTO stock(item_id,location_id,quantity) VALUES(?,?,?) ON CONFLICT(item_id,location_id) DO UPDATE SET quantity=quantity+excluded.quantity",
                          (tx["item_id"],tx["location_id"],tx["quantity"]))
                if tx["related_request_id"] and tx["related_request_id"] < 0:
                    loan_id = -tx["related_request_id"]
                    loan = c.execute("SELECT remaining_qty, quantity FROM loans WHERE id=?", (loan_id,)).fetchone()
                    if loan:
                        cur_rem = loan["remaining_qty"] if loan["remaining_qty"] is not None else loan["quantity"]
                        new_rem = max(0, cur_rem - tx["quantity"])
                        new_status = 'returned' if new_rem == 0 else 'issued'
                        c.execute("UPDATE loans SET remaining_qty=?, status=?, returned_at=? WHERE id=?", (new_rem, new_status, now(), loan_id))

    def reject_transaction(self, tx_id, user):
        self.require_stock()
        with db() as c:
            tx = c.execute("SELECT * FROM transactions WHERE id=? AND status='pending'", (tx_id,)).fetchone()
            if not tx: raise APIError("Pending movement not found",404)
            rejected = c.execute("UPDATE transactions SET status='rejected',confirmed_by=?,confirmed_at=? WHERE id=? AND status='pending'", (user["id"],now(),tx_id))
            if rejected.rowcount != 1: raise APIError("This movement was already handled. Refresh the page.",409)
            if tx["kind"] == "return" and tx["related_request_id"] and tx["related_request_id"] < 0:
                loan_id = -tx["related_request_id"]
                c.execute("UPDATE loans SET status='issued',condition_note='' WHERE id=? AND status='return_pending'", (loan_id,))

    def count_stock(self, item_id, d, user):
        self.require_stock()
        location_id = self.integer(d.get("location_id"), "Location")
        counted = self.integer(d.get("quantity"), "Counted quantity", allow_zero=True)
        reason = str(d.get("reason", "")).strip()
        if not reason:
            raise APIError("Enter a reason or note for the physical count")
        with db() as c:
            item = c.execute("SELECT id FROM items WHERE id=? AND active=1", (item_id,)).fetchone()
            if not item:
                raise APIError("Item not found", 404)
            previous = c.execute("SELECT quantity FROM stock WHERE item_id=? AND location_id=?", (item_id, location_id)).fetchone()
            before = previous[0] if previous else 0
            c.execute("INSERT INTO stock(item_id,location_id,quantity,needs_count,reference_quantity) VALUES(?,?,?,0,NULL) ON CONFLICT(item_id,location_id) DO UPDATE SET quantity=excluded.quantity,needs_count=0,reference_quantity=NULL", (item_id,location_id,counted))
            c.execute("INSERT INTO stock_counts(item_id,location_id,previous_quantity,counted_quantity,counted_by,reason,created_at) VALUES(?,?,?,?,?,?,?)", (item_id,location_id,before,counted,user["id"],reason,now()))
            still_unverified = c.execute("SELECT count(*) FROM stock WHERE item_id=? AND needs_count=1", (item_id,)).fetchone()[0]
            c.execute("UPDATE items SET needs_count=? WHERE id=?", (1 if still_unverified else 0,item_id))

    def update_item(self, item_id, d, user):
        self.require_stock()
        name = str(d.get("name", "")).strip()
        category = str(d.get("category", "")).strip() or "Uncategorized"
        part_number = str(d.get("part_number", "")).strip()
        kind = d.get("kind", "consumable")
        minimum = d.get("min_qty")
        if not name:
            raise APIError("Enter an item name")
        if kind not in ("consumable", "asset"):
            raise APIError("Choose consumable or reusable asset")
        if minimum in ("", None):
            minimum = None
        else:
            minimum = self.integer(minimum, "Minimum quantity", allow_zero=True)
        changes = d.get("location_changes", [])
        if not isinstance(changes, list): raise APIError("Invalid location changes")
        with db() as c:
            moving_sources = {self.integer(change.get("from_id"), "Current location")
                              for change in changes
                              if self.integer(change.get("from_id"), "Current location") != self.integer(change.get("to_id"), "New location")}
            if any(self.integer(change.get("to_id"), "New location") in moving_sources
                   for change in changes
                   if self.integer(change.get("from_id"), "Current location") != self.integer(change.get("to_id"), "New location")):
                raise APIError("Move stock to a destination that is not being moved in this save")
            cur = c.execute("UPDATE items SET name=?,category=?,part_number=?,kind=?,min_qty=? WHERE id=? AND active=1",
                            (name,category,part_number,kind,minimum,item_id))
            if cur.rowcount == 0:
                raise APIError("Item not found",404)
            for change in changes:
                source_id = self.integer(change.get("from_id"), "Current location")
                destination_id = self.integer(change.get("to_id"), "New location")
                if source_id == destination_id: continue
                destination = c.execute("SELECT id FROM locations l WHERE id=? AND active=1 AND NOT EXISTS(SELECT 1 FROM locations child WHERE child.parent_id=l.id)", (destination_id,)).fetchone()
                if not destination: raise APIError("Choose a valid storage location")
                source = c.execute("SELECT quantity,needs_count,reference_quantity FROM stock WHERE item_id=? AND location_id=?", (item_id,source_id)).fetchone()
                if not source: raise APIError("Stock at the selected source location no longer exists")
                target = c.execute("SELECT quantity,needs_count,reference_quantity FROM stock WHERE item_id=? AND location_id=?", (item_id,destination_id)).fetchone()
                quantity = source["quantity"] + (target["quantity"] if target else 0)
                needs_count = bool(source["needs_count"] or (target["needs_count"] if target else 0))
                refs = [x for x in (source["reference_quantity"], target["reference_quantity"] if target else None) if x is not None]
                reference_quantity = sum(refs) if len(refs) == (2 if target else 1) else None
                c.execute("DELETE FROM stock WHERE item_id=? AND location_id=?", (item_id,source_id))
                c.execute("INSERT INTO stock(item_id,location_id,quantity,needs_count,reference_quantity) VALUES(?,?,?,?,?) ON CONFLICT(item_id,location_id) DO UPDATE SET quantity=excluded.quantity,needs_count=excluded.needs_count,reference_quantity=excluded.reference_quantity", (item_id,destination_id,quantity,int(needs_count),reference_quantity))
            assign_loc = d.get("assign_location_id")
            if assign_loc:
                assign_id = self.integer(assign_loc, "Storage location")
                c.execute("INSERT OR IGNORE INTO stock(item_id,location_id,quantity,needs_count) VALUES(?,?,0,1)", (item_id,assign_id))
            remains_unverified = c.execute("SELECT count(*) FROM stock WHERE item_id=? AND needs_count=1", (item_id,)).fetchone()[0]
            c.execute("UPDATE items SET needs_count=? WHERE id=?", (1 if remains_unverified else 0,item_id))

    def create_request(self, d, user):
        lines = d.get("lines", [])
        if not isinstance(lines,list) or not lines: raise APIError("Add at least one requested item")
        project_id = d.get("project_id") or None
        if project_id: project_id = self.integer(project_id,"Project")
        with db() as c:
            ref = self.ref("PR")
            cur = c.execute("INSERT INTO purchase_requests(ref,requester_id,project_id,purpose,status,created_at) VALUES(?,?,?,?, 'pending',?)",
                            (ref,user["id"],project_id,str(d.get("purpose", "")).strip(),now()))
            req_id = cur.lastrowid
            for line in lines:
                item_id = line.get("item_id") or None
                item_name = str(line.get("item_name", "")).strip()
                vendor = str(line.get("vendor", "")).strip()
                product_url = str(line.get("product_url", "")).strip()
                qty = self.integer(line.get("quantity"),"Requested quantity")
                if product_url:
                    parsed_url = urlparse(product_url)
                    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
                        raise APIError("Product links must start with http:// or https://")
                if item_id:
                    item = c.execute("SELECT name FROM items WHERE id=? AND active=1",(self.integer(item_id,"Item"),)).fetchone()
                    if not item: raise APIError("Requested item not found")
                    item_name = item[0]
                if not item_name: raise APIError("Enter an item name for each request line")
                c.execute("INSERT INTO request_lines(request_id,item_id,item_name,quantity,vendor,product_url) VALUES(?,?,?,?,?,?)",(req_id,item_id,item_name,qty,vendor,product_url))

    def set_request_status(self, req_id, status, user):
        self.require_stock()
        if status not in ("approved","rejected","ordered","received"):
            raise APIError("Choose approved, rejected, ordered, or received")
        with db() as c:
            row = c.execute("SELECT status FROM purchase_requests WHERE id=?",(req_id,)).fetchone()
            if not row: raise APIError("Request not found",404)
            allowed = {
                "approved": {"pending", "rejected"},
                "rejected": {"pending", "approved", "ordered", "partially_received"},
                "ordered": {"pending", "approved"},
                "received": {"ordered", "partially_received"}
            }
            if row["status"] not in allowed.get(status, set()):
                raise APIError(f"Cannot change status from {row['status']} to {status}")
            c.execute("UPDATE purchase_requests SET status=?,decision_by=?,decision_at=? WHERE id=?",(status,user["id"],now(),req_id))

    def delete_request(self, req_id, user):
        self.require_stock()
        with db() as c:
            req = c.execute("SELECT * FROM purchase_requests WHERE id=?", (req_id,)).fetchone()
            if not req: raise APIError("Request not found", 404)
            has_inward = c.execute("SELECT count(*) FROM transactions WHERE related_request_id=?", (req_id,)).fetchone()[0]
            if has_inward > 0:
                c.execute("UPDATE purchase_requests SET status='received',decision_by=?,decision_at=? WHERE id=?", (user["id"],now(),req_id))
                return {"ok": True, "message": "Request closed (received stock preserved)"}
            c.execute("DELETE FROM request_lines WHERE request_id=?", (req_id,))
            c.execute("DELETE FROM purchase_requests WHERE id=?", (req_id,))
            return {"ok": True, "message": "Request deleted"}

    def clear_loan(self, loan_id, user):
        self.require_stock()
        with db() as c:
            loan = c.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()
            if not loan: raise APIError("Active checkout not found", 404)
            c.execute("UPDATE loans SET status='returned',remaining_qty=0 WHERE id=?", (loan_id,))
            return {"ok": True, "message": "Checkout cleared"}

    def receive_request_line(self, req_id, d, user):
        self.require_stock()
        qty = self.integer(d.get("quantity"),"Received quantity")
        location_id = self.integer(d.get("location_id"),"Location")
        line_id = self.integer(d.get("line_id"),"Request item")
        with db() as c:
            req = c.execute("SELECT * FROM purchase_requests WHERE id=? AND status IN ('ordered','partially_received')",(req_id,)).fetchone()
            if not req: raise APIError("Only ordered requests can receive stock")
            line = c.execute("SELECT * FROM request_lines WHERE id=? AND request_id=?",(line_id,req_id)).fetchone()
            if not line: raise APIError("Request line not found",404)
            if line["received_quantity"] + qty > line["quantity"]: raise APIError("Received quantity cannot exceed the requested quantity")
            item_id = line["item_id"]
            if not item_id:
                name = str(d.get("name", line["item_name"])).strip()
                existing_item = c.execute("SELECT id FROM items WHERE name=? COLLATE NOCASE AND active=1", (name,)).fetchone()
                if existing_item:
                    item_id = existing_item["id"]
                else:
                    code = f"ITM-{secrets.token_hex(4).upper()}"
                    cur = c.execute("INSERT INTO items(item_code,name,category,kind,unit,created_at) VALUES(?,?,?,'consumable','Nos',?)",
                                    (code,name,str(d.get("category","Uncategorized")).strip() or "Uncategorized",now()))
                    item_id = cur.lastrowid
                c.execute("UPDATE request_lines SET item_id=? WHERE id=?",(item_id,line_id))
            c.execute("INSERT INTO stock(item_id,location_id,quantity) VALUES(?,?,?) ON CONFLICT(item_id,location_id) DO UPDATE SET quantity=quantity+excluded.quantity",(item_id,location_id,qty))
            c.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,purpose,status,created_at,related_request_id,confirmed_by,confirmed_at)
                       VALUES(?,?,?,?,?,?,'Purchase receipt','confirmed',?,?,?,?)""",(self.ref("TX"),"inward",item_id,location_id,qty,user["id"],now(),req_id,user["id"],now()))
            c.execute("UPDATE request_lines SET received_quantity=received_quantity+? WHERE id=?",(qty,line_id))
            remaining = c.execute("SELECT count(*) FROM request_lines WHERE request_id=? AND received_quantity<quantity",(req_id,)).fetchone()[0]
            received_some = c.execute("SELECT sum(received_quantity) FROM request_lines WHERE request_id=?",(req_id,)).fetchone()[0]
            status = "received" if remaining == 0 else ("partially_received" if received_some else "ordered")
            c.execute("UPDATE purchase_requests SET status=? WHERE id=?",(status,req_id))

    def request_return(self, loan_id, d, user):
        qty = self.integer(d.get("quantity"), "Return quantity")
        note = str(d.get("condition", "")).strip()
        location_id = d.get("location_id")
        is_stock = (user["role"] == "stock")
        with db() as c:
            loan = c.execute("SELECT * FROM loans WHERE id=? AND (borrower_id=? OR ?) AND status!='returned'", (loan_id, user["id"], is_stock)).fetchone()
            if not loan: raise APIError("Active item not found for your account", 404)
            rem = loan["remaining_qty"] if loan["remaining_qty"] is not None else loan["quantity"]
            if qty > rem: raise APIError(f"You can only return up to {rem} units")
            loc_id = int(location_id) if location_id else loan["location_id"]
            new_rem = max(0, rem - qty)
            if is_stock:
                new_status = 'returned' if new_rem == 0 else 'issued'
                c.execute("UPDATE loans SET remaining_qty=?, status=?, condition_note='', returned_at=? WHERE id=?", (new_rem, new_status, now(), loan_id))
                c.execute("INSERT INTO stock(item_id,location_id,quantity) VALUES(?,?,?) ON CONFLICT(item_id,location_id) DO UPDATE SET quantity=quantity+excluded.quantity", (loan["item_id"], loc_id, qty))
                c.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,issued_to_id,project_id,purpose,status,condition_note,created_at,confirmed_by,confirmed_at,related_request_id)
                    VALUES(?,?,?,?,?,?,?,?,?,'confirmed',?,?,?,?,?)""", (self.ref("TX"), "return", loan["item_id"], loc_id, qty, user["id"], loan["borrower_id"], loan["project_id"], note or 'Returned to shelf', note, now(), user["id"], now(), -loan_id))
            else:
                c.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,issued_to_id,project_id,purpose,status,condition_note,related_request_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,'pending',?,?,?)""", (self.ref("TX"), "return", loan["item_id"], loc_id, qty, user["id"], loan["borrower_id"], loan["project_id"], note or 'Returned from work', note, -loan_id, now()))
                c.execute("UPDATE loans SET status='return_pending',condition_note=? WHERE id=?", (note, loan_id))

    def consume_loan(self, loan_id, d, user):
        qty = self.integer(d.get("quantity"), "Quantity used")
        note = str(d.get("purpose", "")).strip()
        project_id = d.get("project_id") or None
        if project_id is not None: project_id = self.integer(project_id, "Project")
        with db() as c:
            loan = c.execute("SELECT * FROM loans WHERE id=? AND (borrower_id=? OR ?) AND status!='returned'", (loan_id, user["id"], user["role"] == "stock")).fetchone()
            if not loan: raise APIError("Active item not found for your account", 404)
            rem = loan["remaining_qty"] if loan["remaining_qty"] is not None else loan["quantity"]
            if qty > rem: raise APIError(f"You can only mark up to {rem} units as used")
            proj_id = project_id if project_id is not None else loan["project_id"]
            new_rem = max(0, rem - qty)
            new_consumed = (loan["consumed_qty"] or 0) + qty
            new_status = 'returned' if new_rem == 0 else 'issued'
            c.execute("UPDATE loans SET remaining_qty=?, consumed_qty=?, status=? WHERE id=?", (new_rem, new_consumed, new_status, loan_id))
            purpose_text = f"Used in project: {note}" if note else "Used in project"
            c.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,issued_to_id,project_id,purpose,status,condition_note,related_request_id,created_at,confirmed_by,confirmed_at)
                VALUES(?,?,?,?,?,?,?,?,?,'confirmed',?,?,?,?,?)""",
                (self.ref("TX"), "consumed", loan["item_id"], loan["location_id"], qty, user["id"], loan["borrower_id"], proj_id, purpose_text, note, -loan_id, now(), user["id"], now()))

    def export_csv(self, user):
        with db() as c:
            rows = c.execute("""WITH RECURSIVE location_paths(id,path) AS (
                    SELECT id,name FROM locations WHERE parent_id IS NULL
                    UNION ALL SELECT child.id, parent.path || ' / ' || child.name
                    FROM locations child JOIN location_paths parent ON child.parent_id=parent.id
                )
                SELECT i.item_code,i.name,i.category,i.unit,COALESCE(SUM(s.quantity),0) AS quantity,
                    COALESCE(group_concat(lp.path||': '||s.quantity, '; '),'') AS locations,i.min_qty,i.needs_count
                FROM items i LEFT JOIN stock s ON s.item_id=i.id LEFT JOIN location_paths lp ON lp.id=s.location_id
                WHERE i.active=1 GROUP BY i.id ORDER BY i.name COLLATE NOCASE""").fetchall()
        import csv, io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Item ID","Item","Category","Unit","Total Qty","Locations","Minimum Qty","Count Status"])
        for r in rows:
            writer.writerow([r["item_code"],r["name"],r["category"],r["unit"],r["quantity"],r["locations"],r["min_qty"],"Needs count" if r["needs_count"] else "Confirmed"])
        payload = buf.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type","text/csv; charset=utf-8")
        self.send_header("Content-Disposition","attachment; filename=stock-overview.csv")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def integer(value, label, allow_zero=False):
        try: n = int(value)
        except (TypeError,ValueError): raise APIError(f"{label} must be a whole number")
        if n < (0 if allow_zero else 1): raise APIError(f"{label} must be {('zero or more' if allow_zero else 'at least 1')}")
        return n

    @staticmethod
    def ref(prefix):
        return f"{prefix}-{datetime.now().strftime('%y%m%d')}-{secrets.token_hex(3).upper()}"


if __name__ == "__main__":
    init_db()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 64)
    print(f" Stockroom server is running on port {PORT}")
    print("=" * 64)
    print(f" -> Laptop URL:    http://127.0.0.1:{PORT}/")
    if HOST in ("0.0.0.0", ""):
        addresses = lan_ipv4_addresses()
        if addresses:
            for address in addresses:
                print(f" -> Same Wi-Fi:    http://{address}:{PORT}/")
        else:
            print(" -> Wi-Fi:        Could not detect Wi-Fi IPv4 address.")
        print()
        print(" If other devices cannot connect:")
        print("   Run 'enable_wifi_access.bat' once as Administrator.")
    else:
        print(" LAN access is disabled because STOCK_HOST is set to loopback.")
    print("=" * 64)
    if os.environ.get("STOCK_OPEN_BROWSER") == "1":
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/")).start()
    httpd.serve_forever()
