"""
Migration 0002: Fix ALL schema drift on live TiDB database.

The initial migration was faked on the live server, so some columns
that were added via AddField steps are missing from the real tables.

All operations use IF NOT EXISTS / idempotent SQL so this is safe
to run multiple times.
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
            sql="ALTER TABLE kitchen_optionchoice ADD COLUMN IF NOT EXISTS group_id BIGINT NOT NULL DEFAULT 0",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_optionchoice ADD COLUMN IF NOT EXISTS price_delta DECIMAL(8,2) NOT NULL DEFAULT 0.00",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_cart — add session_key + updated_at if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_cart ADD COLUMN IF NOT EXISTS session_key VARCHAR(40) NULL",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_cart ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT NOW()",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_order — add guest contact + updated_at if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_name VARCHAR(100) NOT NULL DEFAULT ''",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_email VARCHAR(254) NOT NULL DEFAULT ''",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_phone VARCHAR(20) NOT NULL DEFAULT ''",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS delivery_address TEXT",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS special_instructions TEXT",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT NOW()",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_orderitem — add food_name + food_price if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_orderitem ADD COLUMN IF NOT EXISTS food_name VARCHAR(150) NOT NULL DEFAULT ''",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_orderitem ADD COLUMN IF NOT EXISTS food_price DECIMAL(10,2) NOT NULL DEFAULT 0.00",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_cartitem_selected_options — M2M join table
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS kitchen_cartitem_selected_options (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    cartitem_id BIGINT NOT NULL,
                    optionchoice_id BIGINT NOT NULL,
                    UNIQUE KEY uniq_cartitem_choice (cartitem_id, optionchoice_id)
                )
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_orderitem_selected_options — M2M join table
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS kitchen_orderitem_selected_options (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    orderitem_id BIGINT NOT NULL,
                    optionchoice_id BIGINT NOT NULL,
                    UNIQUE KEY uniq_orderitem_choice (orderitem_id, optionchoice_id)
                )
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_cartitem — add added_at + quantity if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_cartitem ADD COLUMN IF NOT EXISTS added_at DATETIME NOT NULL DEFAULT NOW()",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_cartitem ADD COLUMN IF NOT EXISTS quantity INT UNSIGNED NOT NULL DEFAULT 1",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_review — add rating + comment + created_at if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_review ADD COLUMN IF NOT EXISTS rating INT UNSIGNED NOT NULL DEFAULT 5",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_review ADD COLUMN IF NOT EXISTS comment TEXT",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_review ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT NOW()",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # kitchen_payment — add reference + amount + method + status + created_at if missing
        # ---------------------------------------------------------------
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_payment ADD COLUMN IF NOT EXISTS reference VARCHAR(100) NOT NULL DEFAULT ''",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_payment ADD COLUMN IF NOT EXISTS amount DECIMAL(10,2) NOT NULL DEFAULT 0.00",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_payment ADD COLUMN IF NOT EXISTS method VARCHAR(20) NOT NULL DEFAULT 'paystack'",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_payment ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending'",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE kitchen_payment ADD COLUMN IF NOT EXISTS created_at DATETIME NOT NULL DEFAULT NOW()",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ---------------------------------------------------------------
        # django_session — needed for guest/session-based carts
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
    ]
