"""
Management command: fix_db
Run with: python3 manage.py fix_db

Repairs all schema drift on the live TiDB database and seeds data.
Safe to run multiple times (idempotent).
"""
from django.core.management.base import BaseCommand
from django.db import connection


REPAIRS = [
    # --- optionchoice ---
    ("optionchoice.group_id",
     "ALTER TABLE kitchen_optionchoice ADD COLUMN IF NOT EXISTS group_id BIGINT NOT NULL DEFAULT 0"),
    ("optionchoice.price_delta",
     "ALTER TABLE kitchen_optionchoice ADD COLUMN IF NOT EXISTS price_delta DECIMAL(8,2) NOT NULL DEFAULT 0.00"),

    # --- cart ---
    ("cart.session_key",
     "ALTER TABLE kitchen_cart ADD COLUMN IF NOT EXISTS session_key VARCHAR(40) NULL"),
    ("cart.updated_at",
     "ALTER TABLE kitchen_cart ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT NOW()"),

    # --- order ---
    ("order.guest_name",
     "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_name VARCHAR(100) NOT NULL DEFAULT ''"),
    ("order.guest_email",
     "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_email VARCHAR(254) NOT NULL DEFAULT ''"),
    ("order.guest_phone",
     "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS guest_phone VARCHAR(20) NOT NULL DEFAULT ''"),
    ("order.delivery_address",
     "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS delivery_address TEXT"),
    ("order.special_instructions",
     "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS special_instructions TEXT"),
    ("order.updated_at",
     "ALTER TABLE kitchen_order ADD COLUMN IF NOT EXISTS updated_at DATETIME NOT NULL DEFAULT NOW()"),

    # --- orderitem ---
    ("orderitem.food_name",
     "ALTER TABLE kitchen_orderitem ADD COLUMN IF NOT EXISTS food_name VARCHAR(150) NOT NULL DEFAULT ''"),
    ("orderitem.food_price",
     "ALTER TABLE kitchen_orderitem ADD COLUMN IF NOT EXISTS food_price DECIMAL(10,2) NOT NULL DEFAULT 0.00"),

    # --- M2M join tables ---
    ("cartitem_selected_options table", """
        CREATE TABLE IF NOT EXISTS kitchen_cartitem_selected_options (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            cartitem_id BIGINT NOT NULL,
            optionchoice_id BIGINT NOT NULL,
            UNIQUE KEY uniq_ci_opt (cartitem_id, optionchoice_id)
        )
    """),
    ("orderitem_selected_options table", """
        CREATE TABLE IF NOT EXISTS kitchen_orderitem_selected_options (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            orderitem_id BIGINT NOT NULL,
            optionchoice_id BIGINT NOT NULL,
            UNIQUE KEY uniq_oi_opt (orderitem_id, optionchoice_id)
        )
    """),

    # --- django_session (guest cart requires this) ---
    ("django_session table", """
        CREATE TABLE IF NOT EXISTS django_session (
            session_key VARCHAR(40) NOT NULL PRIMARY KEY,
            session_data LONGTEXT NOT NULL,
            expire_date DATETIME(6) NOT NULL
        )
    """),
    ("django_session index", """
        CREATE INDEX IF NOT EXISTS django_session_expire_idx
        ON django_session (expire_date)
    """),
]


SEED_OPTION_GROUPS = {
    'Spice Level': [
        ('Mild', 0.00), ('Medium', 0.00), ('Hot', 0.00), ('Extra Hot', 0.00),
    ],
    'Protein Add-On': [
        ('Extra Chicken', 500.00), ('Extra Beef', 500.00),
        ('Extra Fish', 600.00), ('Extra Prawns', 700.00),
    ],
    'Extra Sides': [
        ('Plantain', 300.00), ('Coleslaw', 200.00),
        ('Moi Moi', 400.00), ('Extra Sauce', 150.00),
    ],
}

RICE_SOUP_GRILL = {
    'Smoky Party Jollof Rice', 'Special Fried Rice',
    'Efo Riro Native Soup', 'Egusi Soup', 'Spiced Suya Platter',
}


class Command(BaseCommand):
    help = 'Repair TiDB schema drift and seed option groups'

    def handle(self, *args, **options):
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('YAJU\'S KITCHEN — DATABASE REPAIR')
        self.stdout.write('=' * 60)

        # ── Step 1: Schema repairs ────────────────────────────────
        self.stdout.write('\n[1/3] Applying schema repairs...')
        with connection.cursor() as cursor:
            for label, sql in REPAIRS:
                try:
                    cursor.execute(sql)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {label}'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ! {label}: {e}'))

        # ── Step 2: Run all Django migrations ────────────────────
        self.stdout.write('\n[2/3] Running Django migrations...')
        from django.core.management import call_command
        try:
            call_command('migrate', '--fake', 'kitchen', '0001', verbosity=0)
            self.stdout.write(self.style.SUCCESS('  ✓ Faked kitchen 0001'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ! Fake 0001: {e}'))

        try:
            call_command('migrate', verbosity=1)
            self.stdout.write(self.style.SUCCESS('  ✓ All migrations applied'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ! migrate: {e}'))

        # ── Step 3: Seed option groups ────────────────────────────
        self.stdout.write('\n[3/3] Seeding option groups...')
        try:
            from kitchen.models import OptionGroup, OptionChoice, FoodItemOption, FoodItem

            groups = {}
            for group_name, choices in SEED_OPTION_GROUPS.items():
                grp, created = OptionGroup.objects.get_or_create(name=group_name)
                groups[group_name] = grp
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created group: {group_name}'))
                for cname, delta in choices:
                    OptionChoice.objects.get_or_create(
                        group=grp, name=cname,
                        defaults={'price_delta': delta}
                    )

            for food in FoodItem.objects.all():
                FoodItemOption.objects.get_or_create(food=food, group=groups['Spice Level'])
                if food.name in RICE_SOUP_GRILL:
                    FoodItemOption.objects.get_or_create(food=food, group=groups['Protein Add-On'])
                    FoodItemOption.objects.get_or_create(food=food, group=groups['Extra Sides'])

            self.stdout.write(self.style.SUCCESS('  ✓ Option groups seeded'))
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'  ✗ Seed error: {e}'))
            self.stdout.write(traceback.format_exc())

        # ── Verification ──────────────────────────────────────────
        self.stdout.write('\n[VERIFY] Checking tables...')
        checks = [
            ('django_session', 'SELECT COUNT(*) FROM django_session'),
            ('kitchen_optionchoice (group_id present)',
             "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_NAME='kitchen_optionchoice' AND COLUMN_NAME='group_id'"),
            ('kitchen_cartitem_selected_options',
             "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_NAME='kitchen_cartitem_selected_options'"),
            ('option_groups', 'SELECT COUNT(*) FROM kitchen_optiongroup'),
            ('option_choices', 'SELECT COUNT(*) FROM kitchen_optionchoice'),
            ('food_option_links', 'SELECT COUNT(*) FROM kitchen_fooditemoption'),
        ]
        with connection.cursor() as cursor:
            for label, sql in checks:
                try:
                    cursor.execute(sql)
                    count = cursor.fetchone()[0]
                    style = self.style.SUCCESS if count > 0 else self.style.ERROR
                    self.stdout.write(style(f'  {label}: {count}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  {label}: ERROR — {e}'))

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('DONE')
        self.stdout.write('=' * 60 + '\n')
