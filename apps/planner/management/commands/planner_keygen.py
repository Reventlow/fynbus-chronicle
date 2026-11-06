"""Print a new key pair for sealing Planner sign-ins (docs/PLANNER.md)."""

from django.core.management.base import BaseCommand

from apps.planner.crypto import generate_keypair


class Command(BaseCommand):
    help = "Generate PLANNER_PUBLIC_KEY / PLANNER_PRIVATE_KEY"

    def handle(self, *args, **options):
        public, private = generate_keypair()
        self.stdout.write("# web.env AND sync.env:")
        self.stdout.write(f"PLANNER_PUBLIC_KEY={public}")
        self.stdout.write("# sync.env ONLY (never the web container):")
        self.stdout.write(f"PLANNER_PRIVATE_KEY={private}")
