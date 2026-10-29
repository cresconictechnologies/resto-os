# Restaurant Management — Codegraph

Generated for future analysis/reference. Maps key modules, routes, and data flow.

## Module Dependency Graph

```
static/index.html + app.js + styles.css
            |
            v
        server/main.py
            |
    +-------+-------+-------+-------+-------+
    v       v       v       v       v       v
routes/  routes/ routes/ routes/ routes/ routes/
billing  excise   inventory kot  orders  owner
    |       |        |        |      |      |
    +---+---+        +---+    +----+   +---+---+
        |                |             |     |
        v                v             v     v
    server/models.py  restoos/init_db  restoos/menu  restoos/store
    server/database.py restoos/cart    restoos/liquor restoos/pos_app
    server/schemas.py restoos/store
    server/seed_data.py
```

## Key Entities

- **restoos/** — core business logic (cart, menu, liquor, POS, store, DB init)
- **server/routes/** — HTTP endpoints (billing, excise, inventory, kot, orders, owner, shifts, tables)
- **server/models.py / schemas.py / database.py** — data layer (SQLite `restoos.db`)
- **static/** — frontend assets (`index.html`, `app.js`, `styles.css`)
- **docs/** — architecture blueprints

## Data Flow

1. Client (`static/app.js`) calls `server/routes/*.py` endpoints.
2. Routes use `server/models.py` + `database.py` (SQLite `restoos.db`).
3. Business logic delegates to `restoos/*.py` (cart calculations, inventory, liquor excise, POS operations).
4. Database seeded by `seed_data.py`; initialized by `restoos/init_db.py`.

## File Registry

| Path | Role |
|---|---|
| restoos/cart.py | Cart/business logic |
| restoos/menu.py | Menu data |
| restoos/liquor.py | Liquor/excise logic |
| restoos/store.py | Store/inventory |
| restoos/pos_app.py | POS entry |
| restoos/init_db.py | DB init |
| server/main.py | App entry |
| server/routes/orders.py | Order endpoints |
| server/routes/billing.py | Billing endpoints |
| server/routes/inventory.py | Inventory endpoints |
| server/routes/owner.py | Owner endpoints |
| server/routes/kot.py | KOT endpoints |
| server/routes/shifts.py | Shift endpoints |
| server/routes/tables.py | Table endpoints |
| server/routes/excise.py | Excise endpoints |
| server/models.py | ORM/domain models |
| server/schemas.py | Pydantic schemas |
| server/database.py | DB connection |
| static/index.html | Client shell |
| static/app.js | Client logic |
