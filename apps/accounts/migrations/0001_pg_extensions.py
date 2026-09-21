"""Enable PostgreSQL extensions (T1.4): uuid-ossp for UUID generation, citext for
case-insensitive email storage (03_DATABASE_DESIGN.md)."""

import django.contrib.postgres.operations as pg_ops
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql='CREATE EXTENSION IF NOT EXISTS "uuid-ossp";',
            reverse_sql='DROP EXTENSION IF EXISTS "uuid-ossp";',
        ),
        pg_ops.CITextExtension(),
    ]
