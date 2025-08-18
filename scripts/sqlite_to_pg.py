# scripts/sqlite_to_pg.py
import os
from sqlalchemy import create_engine, text

# Env vars
sqlite_path = os.environ.get("SQLITE_PATH", "/root/qr_checkout/users.db")
pg_url = os.environ.get("PG_URL", "postgresql+psycopg2://teameventlock:Watermelon1Sugar@localhost/teameventlock")

if not sqlite_path or not pg_url:
    raise ValueError("You must set SQLITE_PATH and PG_URL environment variables.")

# Engines
src = create_engine(f"sqlite:///{sqlite_path}")   # SQLite source
dst = create_engine(pg_url)                       # Postgres destination

def to_bool(v):
    if v is None:
        return False
    try:
        return bool(int(v))  # handles 0/1, "0"/"1"
    except (ValueError, TypeError):
        return bool(v)

def dst_has_fee_percent(conn):
    # Check if "fee_percent" exists on the Postgres "user" table
    q = text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='user'
          AND column_name='fee_percent'
        LIMIT 1
    """)
    return conn.execute(q).first() is not None

def main():
    # -------- Read from SQLite --------
    with src.connect() as s:
        # Does SQLite "user" table have fee_percent?
        cols = [r["name"] for r in s.execute(text("PRAGMA table_info('user')")).mappings()]
        has_fee_src = "fee_percent" in cols

        if has_fee_src:
            users = [
                dict(r) for r in s.execute(text(
                    'SELECT id, email, password, stripe_account_id, '
                    'COALESCE(charges_enabled, 0) AS charges_enabled, '
                    'COALESCE(details_submitted, 0) AS details_submitted, '
                    'COALESCE(fee_percent, 12.0) AS fee_percent '
                    'FROM "user"'
                )).mappings().all()
            ]
        else:
            users = [
                dict(r) for r in s.execute(text(
                    'SELECT id, email, password, stripe_account_id, '
                    'COALESCE(charges_enabled, 0) AS charges_enabled, '
                    'COALESCE(details_submitted, 0) AS details_submitted '
                    'FROM "user"'
                )).mappings().all()
            ]
            for u in users:
                u["fee_percent"] = 12.0  # default if src didn’t have it

        tickets = [
            dict(r) for r in s.execute(text(
                "SELECT id, name, price, user_id FROM ticket"
            )).mappings().all()
        ]

    # Normalize booleans for Postgres
    for u in users:
        u["charges_enabled"]   = to_bool(u.get("charges_enabled"))
        u["details_submitted"] = to_bool(u.get("details_submitted"))

    # -------- Write to Postgres (UPSERT) --------
    with dst.begin() as d:
        # Detect if destination has fee_percent
        has_fee_dst = dst_has_fee_percent(d)

        if has_fee_dst:
            insert_user = text("""
                INSERT INTO "user" (id, email, password, stripe_account_id,
                                    charges_enabled, details_submitted, fee_percent)
                VALUES (:id, :email, :password, :stripe_account_id,
                        :charges_enabled, :details_submitted, :fee_percent)
                ON CONFLICT (id) DO UPDATE SET
                    email             = EXCLUDED.email,
                    password          = EXCLUDED.password,
                    stripe_account_id = EXCLUDED.stripe_account_id,
                    charges_enabled   = EXCLUDED.charges_enabled,
                    details_submitted = EXCLUDED.details_submitted,
                    fee_percent       = EXCLUDED.fee_percent
            """)
        else:
            # If your PG table doesn't have fee_percent yet
            insert_user = text("""
                INSERT INTO "user" (id, email, password, stripe_account_id,
                                    charges_enabled, details_submitted)
                VALUES (:id, :email, :password, :stripe_account_id,
                        :charges_enabled, :details_submitted)
                ON CONFLICT (id) DO UPDATE SET
                    email             = EXCLUDED.email,
                    password          = EXCLUDED.password,
                    stripe_account_id = EXCLUDED.stripe_account_id,
                    charges_enabled   = EXCLUDED.charges_enabled,
                    details_submitted = EXCLUDED.details_submitted
            """)

        for u in users:
            d.execute(insert_user, u)

        insert_ticket = text("""
            INSERT INTO ticket (id, name, price, user_id)
            VALUES (:id, :name, :price, :user_id)
            ON CONFLICT (id) DO UPDATE SET
                name   = EXCLUDED.name,
                price  = EXCLUDED.price,
                user_id= EXCLUDED.user_id
        """)
        for t in tickets:
            d.execute(insert_ticket, t)

    print(f"✅ Migrated {len(users)} users and {len(tickets)} tickets.")

if __name__ == "__main__":
    main()
