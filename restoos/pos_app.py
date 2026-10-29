#!/usr/bin/env python3
import sqlite3, subprocess, sys, os, json
DB = "restoos.db"
BASE = os.path.dirname(os.path.abspath(__file__))

def db(): return sqlite3.connect(DB)

print("POS ready. Menu items: SKU, name, price. Done for now.", file=sys.stderr)
sys.path.insert(0, BASE)
from menu import list as lmenu
