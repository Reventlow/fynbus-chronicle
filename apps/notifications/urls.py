"""URL configuration for the notifications application."""

from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("partials/badge/", views.badge, name="partial-badge"),
    path("partials/panel/", views.panel, name="partial-panel"),
]
