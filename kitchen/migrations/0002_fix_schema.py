"""
Migration 0002: Fix schema drift on live TiDB database.

The initial migration was "faked" on the live server, which means
Django considers it done but certain columns (like group_id on
kitchen_optionchoice) may be genuinely missing from the actual table.

This migration uses RunSQL with IF NOT EXISTS so it is 100% safe
to run multiple times and will not fail if columns already exist.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kitchen', '0001_initial'),
    ]

    operations = [
        # ---------------------------------------------------------------
        # kitchen_optionchoice — add group_id + price_delta if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_optionchoice
                ADD COLUMN IF NOT EXISTS group_id BIGINT NOT NULL DEFAULT 0
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_optionchoice
                ADD COLUMN IF NOT EXISTS price_delta DECIMAL(8,2) NOT NULL DEFAULT 0.00
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_cart — add session_key + updated_at if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_cart
                ADD COLUMN IF NOT EXISTS session_key VARCHAR(40) NULL
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_cart
                ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT NOW()
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_order — add guest contact fields + updated_at if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_order
                ADD COLUMN IF NOT EXISTS guest_name VARCHAR(100) NOT NULL DEFAULT ''
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_order
                ADD COLUMN IF NOT EXISTS guest_email VARCHAR(254) NOT NULL DEFAULT ''
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_order
                ADD COLUMN IF NOT EXISTS guest_phone VARCHAR(20) NOT NULL DEFAULT ''
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_order
                ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT NOW()
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_orderitem — add food_name + food_price if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_orderitem
                ADD COLUMN IF NOT EXISTS food_name VARCHAR(150) NOT NULL DEFAULT ''
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE kitchen_orderitem
                ADD COLUMN IF NOT EXISTS food_price DECIMAL(10,2) NOT NULL DEFAULT 0.00
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # django_session — create if the table doesn't exist at all
        # (needed for guest/session-based carts)
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS django_session (
                    session_key VARCHAR(40) NOT NULL PRIMARY KEY,
                    session_data LONGTEXT NOT NULL,
                    expire_date DATETIME(6) NOT NULL
                )
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS django_session_expire_date_idx
                ON django_session (expire_date)
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
