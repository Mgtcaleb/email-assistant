import os, sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "monitor.db"

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY, marketplace TEXT, status TEXT, eta TEXT,
        last_message_id TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS processed (
        message_id TEXT PRIMARY KEY, processed_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    return con

def is_processed(con, message_id):
    return con.execute("SELECT 1 FROM processed WHERE message_id=?", (message_id,)).fetchone() is not None

def mark_processed(con, message_id):
    con.execute("INSERT OR IGNORE INTO processed(message_id) VALUES(?)", (message_id,))

def get_order(con, order_id):
    row = con.execute("SELECT order_id,marketplace,status,eta FROM orders WHERE order_id=?", (order_id,)).fetchone()
    if not row: return None
    return dict(zip(["order_id","marketplace","status","eta"], row))

def save_order(con, order, message_id):
    con.execute("""INSERT INTO orders(order_id,marketplace,status,eta,last_message_id)
        VALUES(?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET
        marketplace=excluded.marketplace,status=excluded.status,
        eta=COALESCE(excluded.eta,orders.eta),last_message_id=excluded.last_message_id,
        updated_at=CURRENT_TIMESTAMP""",
        (order["order_id"], order["marketplace"], order["status"], order.get("eta"), message_id))
