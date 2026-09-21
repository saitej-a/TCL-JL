"""06 §2.1 entity table: is_verified flag + lifecycle audit timestamps on User.

Hand-authored (plan executor hint): AddField with auto_now_add cannot be
auto-generated without an interactive one-off default. Dev DB has zero users,
so timezone.now as a throwaway column default is a no-op backfill.
"""

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_alter_user_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
