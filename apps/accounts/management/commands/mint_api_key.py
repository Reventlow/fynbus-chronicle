"""Mint an API key for a user from the command line.

Usage:

    python manage.py mint_api_key alice --scope=read --label="Claude MCP"
    python manage.py mint_api_key alice --scope=write

Prints the raw key on stdout exactly once. Use it for bootstrap, break-glass,
or scripted key rotation.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import APIKey


class Command(BaseCommand):
    help = "Mint a new API key for the given user and print it once on stdout."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Username of the key owner.")
        parser.add_argument(
            "--scope",
            choices=[APIKey.Scope.READ, APIKey.Scope.WRITE],
            default=APIKey.Scope.READ,
            help="Key scope (default: read).",
        )
        parser.add_argument(
            "--label",
            default="",
            help="Optional human label, e.g. 'Claude MCP – laptop'.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as exc:
            raise CommandError(f"No user with username {options['username']!r}") from exc

        api_key, raw = APIKey.generate(
            user=user,
            scope=options["scope"],
            label=options["label"],
        )

        self.stdout.write(self.style.SUCCESS("API key minted."))
        self.stdout.write(f"  user:   {user.username}")
        self.stdout.write(f"  scope:  {api_key.get_scope_display()}")
        self.stdout.write(f"  label:  {api_key.label or '(none)'}")
        self.stdout.write(f"  prefix: {api_key.prefix}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Raw key (shown only once — copy now):"))
        self.stdout.write(raw)
