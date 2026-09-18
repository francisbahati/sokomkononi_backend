from django.db import migrations, models


def tombstone_deleted_user_emails(apps, schema_editor):
    """
    Before we add a global unique index on `email`, soft-deleted users
    may be holding emails that collide with active users. Move them
    into `deleted_email` and clear `email` so the unique index can
    be created and new registrations can reuse the freed addresses.
    """
    User = apps.get_model("accounts", "User")

    qs = (
        User.objects
        .filter(is_deleted=True)
        .exclude(email__isnull=True)
    )

    for user in qs.iterator():
        user.deleted_email = user.email
        user.email = None
        user.save(update_fields=["email", "deleted_email"])


def reverse_tombstone(apps, schema_editor):
    """
    Reverse: put the tombstoned email back into `email` for any
    soft-deleted user whose email is currently empty.
    """
    User = apps.get_model("accounts", "User")

    qs = (
        User.objects
        .filter(is_deleted=True)
        .exclude(deleted_email__isnull=True)
    )

    for user in qs.iterator():
        if not user.email:
            user.email = user.deleted_email
            user.deleted_email = None
            user.save(update_fields=["email", "deleted_email"])


class Migration(migrations.Migration):

    dependencies = [
        (
            "accounts",
            "0005_alter_user_options_alter_user_managers_and_more",
        ),
    ]

    operations = [
        # 1. Add the tombstone field.
        migrations.AddField(
            model_name="user",
            name="deleted_email",
            field=models.EmailField(
                blank=True,
                null=True,
                verbose_name="Barua pepe ya awali",
            ),
        ),

        # 2. Free up emails held by soft-deleted users so the unique
        #    index we add next won't fail.
        migrations.RunPython(
            tombstone_deleted_user_emails,
            reverse_code=reverse_tombstone,
        ),

        # 3. Drop the partial unique constraint — the field itself is
        #    now unconditionally unique.
        migrations.RemoveConstraint(
            model_name="user",
            name="unique_active_user_email",
        ),

        # 4. Make the email field unique.
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                null=True,
                unique=True,
                verbose_name="Barua pepe",
            ),
        ),
    ]