from django.apps import AppConfig


class CvesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cves"
    label = "cves"
    verbose_name = "Sårbarheder"
