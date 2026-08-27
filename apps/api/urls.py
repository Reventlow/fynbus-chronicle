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
        "weeklogs/<int:year>/<int:week>/helpdesk-age/",
        views.weeklog_helpdesk_age,
        name="weeklog-helpdesk-age",
    ),
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
        "priority-items/<int:loser_id>/merge-into/<int:winner_id>/",
        views.priority_item_merge,
        name="priority-item-merge",
    ),
    path(
        "weeklogs/<int:year>/<int:week>/incidents/",
        views.incident_create,
        name="incident-create",
    ),
    # Feature requests
    path("feature-requests/", views.feature_requests_list, name="feature-requests-list"),
    path("feature-requests/create/", views.feature_request_create, name="feature-request-create"),
    path("feature-requests/<int:pk>/", views.feature_request_detail, name="feature-request-detail"),
    path("feature-requests/<int:pk>/update/", views.feature_request_update, name="feature-request-update"),
    path("feature-requests/<int:pk>/solve/", views.feature_request_solve, name="feature-request-solve"),
]
