"""ServiceDesk page: the open and closed tickets from the local mirror,
sorted into mine / not assigned / everybody else's, and links from a
ticket to a Chronicle priority or case."""

from django.apps import AppConfig


class ServicedeskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.servicedesk"
    verbose_name = "ServiceDesk"
