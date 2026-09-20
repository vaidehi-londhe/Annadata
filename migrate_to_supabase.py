import sqlite3
import psycopg2
from getpass import getpass


# -----------------------------
# SUPABASE DATABASE DETAILS
# -----------------------------

HOST = "aws-0-ap-northeast-2.pooler.supabase.com"
PORT = 5432
DATABASE = "postgres"
USER = "postgres.ujiavoxmwdwjbfdgizhc"


# -----------------------------
# ASK FOR PASSWORD SAFELY
# -----------------------------

PASSWORD = getpass("Enter your Supabase database password: ")


# -----------------------------
# CONNECT TO LOCAL SQLITE
# -----------------------------

sqlite_conn = sqlite3.connect("annadata.db")
sqlite_conn.row_factory = sqlite3.Row

sqlite_cursor = sqlite_conn.cursor()


# -----------------------------
# CONNECT TO SUPABASE
# -----------------------------

pg_conn = psycopg2.connect(
    host=HOST,
    port=PORT,
    database=DATABASE,
    user=USER,
    password=PASSWORD
)

pg_cursor = pg_conn.cursor()


# -----------------------------
# TABLES TO MIGRATE
# -----------------------------

tables = [
    "users",
    "farmer_profile",
    "schemes",
    "crops",
    "saved_schemes",
    "crop_recommendations",
    "chat_messages",
    "farm_task_actions",
]


# -----------------------------
# MIGRATE EACH TABLE
# -----------------------------

for table in tables:

    # Check whether table exists in SQLite
    sqlite_cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table,)
    )

    exists = sqlite_cursor.fetchone()

    if not exists:
        print(f"SKIPPED: {table} (not present in local database)")
        continue

    # Get columns from SQLite
    sqlite_cursor.execute(f'PRAGMA table_info("{table}")')
    columns_info = sqlite_cursor.fetchall()

    columns = [row["name"] for row in columns_info]

    # Get rows
    sqlite_cursor.execute(f'SELECT * FROM "{table}"')
    rows = sqlite_cursor.fetchall()

    print(f"\n{table}: {len(rows)} rows found")

    if not rows:
        continue

    column_names = ", ".join(f'"{col}"' for col in columns)
    placeholders = ", ".join(["%s"] * len(columns))

    insert_sql = f"""
        INSERT INTO "{table}" ({column_names})
        VALUES ({placeholders})
    """

    for row in rows:
        values = [row[col] for col in columns]
        pg_cursor.execute(insert_sql, values)

    print(f"  ✓ {len(rows)} rows copied")


# -----------------------------
# RESET IDENTITY SEQUENCES
# -----------------------------

print("\nUpdating ID sequences...")

for table in tables:

    # Check if table exists in Supabase
    pg_cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        )
        """,
        (table,)
    )

    if not pg_cursor.fetchone()[0]:
        continue

    try:
        pg_cursor.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('public."{table}"', 'id'),
                COALESCE(MAX(id), 1),
                MAX(id) IS NOT NULL
            )
            FROM public."{table}"
            """
        )
    except Exception:
        pg_conn.rollback()
        print(f"  Sequence update skipped for {table}")


# -----------------------------
# COMMIT EVERYTHING
# -----------------------------

pg_conn.commit()


# -----------------------------
# SHOW FINAL COUNTS
# -----------------------------

print("\n================================")
print("   MIGRATION COMPLETED")
print("================================")

for table in tables:

    try:
        pg_cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = pg_cursor.fetchone()[0]
        print(f"{table}: {count}")
    except Exception:
        pg_conn.rollback()

pg_cursor.close()
pg_conn.close()

sqlite_cursor.close()
sqlite_conn.close()

print("\nDone!")