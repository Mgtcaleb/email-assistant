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
    con.execute("""CREATE TABLE IF NOT EXISTS daily_summaries (
        summary_date TEXT PRIMARY KEY,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
        count_today INTEGER DEFAULT 0,
        count_day1 INTEGER DEFAULT 0,
        count_day2 INTEGER DEFAULT 0,
        details TEXT
    )""")
    try:
        con.execute("ALTER TABLE orders ADD COLUMN eta_date TEXT")
    except sqlite3.OperationalError:
        pass
    return con

def is_processed(con, message_id):
    return con.execute("SELECT 1 FROM processed WHERE message_id=?", (message_id,)).fetchone() is not None

def mark_processed(con, message_id):
    con.execute("INSERT OR IGNORE INTO processed(message_id) VALUES(?)", (message_id,))

def get_order(con, order_id):
    row = con.execute("SELECT order_id,marketplace,status,eta,eta_date FROM orders WHERE order_id=?", (order_id,)).fetchone()
    if not row: return None
    return dict(zip(["order_id","marketplace","status","eta","eta_date"], row))

def save_order(con, order, message_id):
    eta_date = order.get("eta_date")
    con.execute("""INSERT INTO orders(order_id,marketplace,status,eta,eta_date,last_message_id)
        VALUES(?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET
        marketplace=excluded.marketplace,status=excluded.status,
        eta=COALESCE(excluded.eta,orders.eta),
        eta_date=COALESCE(excluded.eta_date,orders.eta_date),
        last_message_id=excluded.last_message_id,
        updated_at=CURRENT_TIMESTAMP""",
        (order["order_id"], order["marketplace"], order["status"], order.get("eta"), eta_date, message_id))

def get_active_orders(con, marketplace="amazon.in"):
    """Returns active orders for a marketplace excluding terminal cancelled/returned orders."""
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT order_id, marketplace, status, eta, eta_date, updated_at
        FROM orders
        WHERE marketplace = ? AND status NOT IN ('CANCELLED', 'RETURNED')
        ORDER BY updated_at DESC
    """, (marketplace,)).fetchall()
    return [dict(r) for r in rows]

def has_sent_summary_today(con, date_str: str) -> bool:
    row = con.execute("SELECT 1 FROM daily_summaries WHERE summary_date=?", (date_str,)).fetchone()
    return row is not None

def record_summary_sent(con, date_str: str, count_today: int, count_day1: int, count_day2: int, details: str = ""):
    con.execute("""
        INSERT INTO daily_summaries(summary_date, sent_at, count_today, count_day1, count_day2, details)
        VALUES(?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
        ON CONFLICT(summary_date) DO UPDATE SET
        sent_at=CURRENT_TIMESTAMP, count_today=excluded.count_today,
        count_day1=excluded.count_day1, count_day2=excluded.count_day2,
        details=excluded.details
    """, (date_str, count_today, count_day1, count_day2, details))
