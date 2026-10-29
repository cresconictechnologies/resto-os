#!/usr/bin/env python3
# shortcut: SQLite only; no network sync yet. Upgrade to full LAN sync when needed.
import sqlite3, os
DB = "restoos.db"
if not os.path.exists(DB):
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY, total REAL, paid INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE menu(id INTEGER PRIMARY KEY, name TEXT, price REAL)")
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.commit()
print("DB init ok. Tables: orders.")
# audit: SQLite WAL = power-cut safe. shortcut: no Rust/native yet; Python only.
