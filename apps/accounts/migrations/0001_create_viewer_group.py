"""
Data migration to create the Viewer auth group.
"""

from django.db import migrations


def create_viewer_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Viewer")


def remove_viewer_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Viewer").delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_viewer_group, remove_viewer_group),
    ]
