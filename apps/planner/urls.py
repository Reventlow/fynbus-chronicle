"""URLs for the Planner board (mounted at /planner/)."""

from django.urls import path

from . import views

app_name = "planner"

urlpatterns = [
    path("", views.board, name="board"),
    path("status/", views.status, name="status"),
    path("sync/", views.sync_now, name="sync-now"),
    path("connect/", views.connect, name="connect"),
    # Registered as the redirect URI on the "Chronicle Planner" app.
    path("connect/callback/", views.connect_callback, name="connect-callback"),
    path("disconnect/", views.disconnect, name="disconnect"),
]
