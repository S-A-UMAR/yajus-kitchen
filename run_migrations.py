#!/usr/bin/env python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yajus_kitchen.settings")
django.setup()

from django.core.management import call_command

# First, fake the kitchen app migrations since those tables already exist
try:
    call_command('migrate', '--fake', 'kitchen')
except Exception as e:
    print(f"Note (kitchen migrations already applied: {e}")

# Now run all other migrations normally
call_command('migrate')

# Now seed the database with sample data
from seed_data import seed
seed()
