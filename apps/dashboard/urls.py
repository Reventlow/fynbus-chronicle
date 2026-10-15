"""URL configuration for the dashboard application."""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="index"),
    path("statistik/", views.StatisticsView.as_view(), name="statistics"),
    path("statistik/export/<str:fmt>/", views.statistics_export, name="statistics-export"),
    path("statistik/deling/", views.statistics_share, name="statistics-share"),
    # Public share links: no login, the token is the key.
    path("statistik/delt/<str:token>/data.json", views.statistics_shared_json, name="statistics-shared-json"),
    path("statistik/delt/<str:token>/vejledning.md", views.statistics_shared_guide, name="statistics-shared-guide"),
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
        "partials/open-age/",
        views.OpenAgePartialView.as_view(),
        name="partial-open-age",
    ),
    path(
        "partials/open-categories/",
        views.OpenCategoriesPartialView.as_view(),
        name="partial-open-categories",
    ),
    path(
        "partials/open-technicians/",
        views.OpenTechniciansPartialView.as_view(),
        name="partial-open-technicians",
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
    path(
        "partials/latest-change/",
        views.LatestChangePartialView.as_view(),
        name="partial-latest-change",
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
