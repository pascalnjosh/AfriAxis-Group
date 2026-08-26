from django.db import migrations, models
from django.utils import timezone


def populate_created_at(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")

    UserProfile.objects.filter(
        created_at__isnull=True
    ).update(
        created_at=timezone.now()
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "accounts",
            "0002_userprofile_bio_userprofile_branch_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            populate_created_at,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
            ),
        ),
    ]
