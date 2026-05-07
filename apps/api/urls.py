"""URL configuration for the Chronicle JSON API.

Mounted under ``/api/v1/`` from chronicle/urls.py.
"""

from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    # Read
    path("weeklogs/", views.weeklog_list, name="weeklog-list"),
    path("weeklogs/current/", views.weeklog_current, name="weeklog-current"),
    path("weeklogs/<int:year>/<int:week>/", views.weeklog_detail, name="weeklog-detail"),
    path("incidents/", views.incidents_recent, name="incidents-recent"),
    path("oncall/current/", views.oncall_current, name="oncall-current"),
    path("helpdesk/data/", views.helpdesk_data, name="helpdesk-data"),
    path("changelog/latest/", views.changelog_latest, name="changelog-latest"),
    # Write
    path(
        "weeklogs/<int:year>/<int:week>/priority-items/",
        views.priority_item_create,
        name="priority-item-create",
    ),
    path(
        "priority-items/<int:item_id>/",
        views.priority_item_update,
        name="priority-item-update",
    ),
    path(
        "priority-items/<int:item_id>/history/",
        views.priority_item_history,
        name="priority-item-history",
    ),
    path(
        "weeklogs/<int:year>/<int:week>/priority-items/carry/",
        views.weeklog_carry_priorities,
        name="weeklog-carry-priorities",
    ),
    path(
        "weeklogs/<int:year>/<int:week>/incidents/",
        views.incident_create,
        name="incident-create",
    ),
]
