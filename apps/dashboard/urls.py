"""URL configuration for the dashboard application."""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="index"),
    # HTMX partials
    path(
        "partials/current-week/",
        views.CurrentWeekPartialView.as_view(),
        name="partial-current-week",
    ),
    path(
        "partials/helpdesk-stats/",
        views.HelpdeskStatsPartialView.as_view(),
        name="partial-helpdesk-stats",
    ),
    path(
        "partials/helpdesk-chart/",
        views.HelpdeskChartPartialView.as_view(),
        name="partial-helpdesk-chart",
    ),
    path(
        "partials/helpdesk-flow-chart/",
        views.HelpdeskFlowChartPartialView.as_view(),
        name="partial-helpdesk-flow-chart",
    ),
    path(
        "partials/incidents/",
        views.IncidentsPartialView.as_view(),
        name="partial-incidents",
    ),
    path(
        "partials/oncall/",
        views.OnCallPartialView.as_view(),
        name="partial-oncall",
    ),
    path(
        "partials/footer-version/",
        views.FooterVersionPartialView.as_view(),
        name="partial-footer-version",
    ),
    # Task timeline
    path(
        "partials/task-timeline/",
        views.TaskTimelinePartialView.as_view(),
        name="task-timeline-partial",
    ),
    # Actions
    path(
        "api/sync-servicedesk/",
        views.sync_servicedesk_stats,
        name="sync-servicedesk",
    ),
    # Chart data APIs
    path("api/helpdesk-data/", views.helpdesk_chart_data, name="api-helpdesk-data"),
    path(
        "api/task-timeline-data/",
        views.task_timeline_chart_data,
        name="api-task-timeline-data",
    ),
    # Documentation
    path("docs/", views.DocsIndexView.as_view(), name="docs-index"),
    path("docs/<slug:slug>/", views.DocsPageView.as_view(), name="docs-page"),
]
