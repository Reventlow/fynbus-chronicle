"""Make the missing PDF renditions of course presentations.

Presentations get their PDF at upload; this catches the ones uploaded
before the player existed (1.20.0) or whose conversion failed.
``--all`` redoes every presentation.
"""

from django.core.management.base import BaseCommand

from apps.courses.convert import make_preview
from apps.courses.models import CourseMaterial


class Command(BaseCommand):
    help = "Convert course presentations that have no PDF rendition yet."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Redo every presentation, not only the missing ones.")

    def handle(self, *args, **options):
        qs = CourseMaterial.objects.filter(kind=CourseMaterial.Kind.SLIDES)
        if not options["all"]:
            qs = qs.filter(preview="")
        done = failed = 0
        for item in qs:
            error = make_preview(item)
            if error:
                failed += 1
                self.stderr.write(f"{item.key} {item.title!r}: {error}")
            else:
                done += 1
                self.stdout.write(f"{item.key} {item.title!r}: ok")
        self.stdout.write(f"{done} converted, {failed} failed")
