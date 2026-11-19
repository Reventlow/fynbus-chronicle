"""Give the Sites framework's default site Chronicle's own name.

allauth puts the site name in front of its e-mail subjects
("[example.com] …"). The site was never renamed in production, so the
default is replaced here, but only while it is still Django's
placeholder: a site an admin already edited is left alone. On a fresh
database no site exists yet (Django adds example.com after migrating, and
only when there is none), so the site is created here with the right name.
"""

from django.conf import settings
from django.core.management.color import no_style
from django.db import migrations

PLACEHOLDER = "example.com"
DOMAIN = "chronicle.fynbus.net"
NAME = "FynBus Chronicle"


def rename_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    db = schema_editor.connection.alias
    if not Site.objects.using(db).exists():
        Site.objects.using(db).create(pk=settings.SITE_ID, domain=DOMAIN, name=NAME)
        # As django.contrib.sites does: an explicit pk leaves the sequence behind.
        sequence_sql = schema_editor.connection.ops.sequence_reset_sql(no_style(), [Site])
        with schema_editor.connection.cursor() as cursor:
            for sql in sequence_sql:
                cursor.execute(sql)
        return
    Site.objects.using(db).filter(pk=settings.SITE_ID, domain=PLACEHOLDER).update(domain=DOMAIN, name=NAME)


def restore_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.using(schema_editor.connection.alias).filter(pk=settings.SITE_ID, domain=DOMAIN).update(domain=PLACEHOLDER, name=PLACEHOLDER)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_apikey"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [migrations.RunPython(rename_site, restore_site)]
