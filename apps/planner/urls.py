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
    path("me/connect/", views.connect_me, name="connect-me"),
    path("me/disconnect/", views.disconnect_me, name="disconnect-me"),
    path("task/<str:task_id>/complete/", views.complete, name="complete"),
    path("task/<str:task_id>/move/", views.move, name="move"),
    path("task/<str:task_id>/link/", views.link, name="link"),
    path("bucket/<str:bucket_id>/add/", views.create, name="create"),
    path("change/<int:pk>/", views.change, name="change"),
]
