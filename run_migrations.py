#!/usr/bin/env python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yajus_kitchen.settings")
django.setup()

from django.core.management import call_command
from django.db import connection

# Check if 0001_initial is already applied (if not, fake it)
with connection.cursor() as cursor:
    try:
        cursor.execute("SELECT name FROM django_migrations WHERE app='kitchen' AND name='0001_initial'")
        initial_applied = cursor.fetchone() is not None
    except Exception:
        initial_applied = False

if not initial_applied:
    print("Faking kitchen 0001_initial migration (tables already exist)...")
    try:
        call_command('migrate', '--fake', 'kitchen', '0001')
    except Exception as e:
        print(f"Note: {e}")

# Now run all remaining migrations normally
call_command('migrate')

# Now seed the database with sample data - force update if needed
try:
    import seed_data
    seed_data.seed()
    print("Seeding completed successfully!")
except Exception as e:
    print(f"Seeding encountered an error (but migrations still ran): {e}")
