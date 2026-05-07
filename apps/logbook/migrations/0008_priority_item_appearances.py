"""Refactor PriorityItem to support multi-week appearances.

Steps:
  1. Rename ``weeklog`` → ``origin_weeklog`` and update related_name.
  2. Add ``last_active_at`` / ``auto_closed`` / ``closed_at`` to PriorityItem.
  3. Create the new PriorityItemAppearance table.
  4. Data migration: copy existing PriorityItem.description / .order onto a
     freshly-created appearance for each item's origin weeklog.
  5. Drop ``description`` and ``order`` from PriorityItem.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_appearances(apps, schema_editor):
    """Create one appearance per existing PriorityItem with the old description."""
    PriorityItem = apps.get_model("logbook", "PriorityItem")
    PriorityItemAppearance = apps.get_model("logbook", "PriorityItemAppearance")
    appearances = []
    for item in PriorityItem.objects.all():
        appearances.append(
            PriorityItemAppearance(
                priority_item=item,
                weeklog=item.origin_weeklog,
                description=item.description or "",
                order=item.order or 0,
            )
        )
    if appearances:
        PriorityItemAppearance.objects.bulk_create(appearances)


def unbackfill_appearances(apps, schema_editor):
    """Reverse: dump description back to PriorityItem from each item's origin appearance."""
    PriorityItem = apps.get_model("logbook", "PriorityItem")
    PriorityItemAppearance = apps.get_model("logbook", "PriorityItemAppearance")
    for item in PriorityItem.objects.all():
        appearance = (
            PriorityItemAppearance.objects.filter(
                priority_item=item, weeklog=item.origin_weeklog
            ).first()
        )
        if appearance is not None:
            item.description = appearance.description
            item.order = appearance.order
            item.save(update_fields=["description", "order"])


class Migration(migrations.Migration):

    dependencies = [
        ("logbook", "0007_add_default_to_meeting_fields"),
    ]

    operations = [
        # ---- 1. Rename FK ------------------------------------------------
        migrations.RenameField(
            model_name="priorityitem",
            old_name="weeklog",
            new_name="origin_weeklog",
        ),
        migrations.AlterField(
            model_name="priorityitem",
            name="origin_weeklog",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="originated_priority_items",
                to="logbook.weeklog",
                verbose_name="Oprindelig ugelog",
                help_text="Den uge opgaven først blev oprettet i.",
            ),
        ),
        # ---- 2. New PriorityItem fields ----------------------------------
        migrations.AddField(
            model_name="priorityitem",
            name="last_active_at",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                verbose_name="Sidst aktiv",
                help_text=(
                    "Bumpes ved bruger-handling (statusskift, redigering, "
                    "ny uge-beskrivelse). Drevet af 6-ugers auto-luk-reglen."
                ),
            ),
        ),
        migrations.AddField(
            model_name="priorityitem",
            name="auto_closed",
            field=models.BooleanField(default=False, verbose_name="Auto-lukket"),
        ),
        migrations.AddField(
            model_name="priorityitem",
            name="closed_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Lukket"
            ),
        ),
        migrations.AlterModelOptions(
            name="priorityitem",
            options={
                "ordering": ["-last_active_at", "-priority", "title"],
                "verbose_name": "Prioriteret opgave",
                "verbose_name_plural": "Prioriterede opgaver",
            },
        ),
        migrations.AddIndex(
            model_name="priorityitem",
            index=models.Index(
                fields=["status", "last_active_at"],
                name="logbook_pri_status_last_active_idx",
            ),
        ),
        # ---- 3. New PriorityItemAppearance model -------------------------
        migrations.CreateModel(
            name="PriorityItemAppearance",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Hvad skete der med opgaven i denne uge?",
                        verbose_name="Beskrivelse",
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(default=0, verbose_name="Rækkefølge"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "priority_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="appearances",
                        to="logbook.priorityitem",
                        verbose_name="Opgave",
                    ),
                ),
                (
                    "weeklog",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="priority_appearances",
                        to="logbook.weeklog",
                        verbose_name="Ugelog",
                    ),
                ),
            ],
            options={
                "verbose_name": "Opgave-tilknytning",
                "verbose_name_plural": "Opgave-tilknytninger",
                "ordering": ["order", "created_at"],
                "unique_together": {("priority_item", "weeklog")},
            },
        ),
        migrations.AddIndex(
            model_name="priorityitemappearance",
            index=models.Index(
                fields=["weeklog", "order"], name="logbook_pri_appear_week_order_idx"
            ),
        ),
        # ---- 4. Backfill -------------------------------------------------
        migrations.RunPython(backfill_appearances, unbackfill_appearances),
        # ---- 5. Drop old fields off PriorityItem --------------------------
        migrations.RemoveField(model_name="priorityitem", name="description"),
        migrations.RemoveField(model_name="priorityitem", name="order"),
    ]
