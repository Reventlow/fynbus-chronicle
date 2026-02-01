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
        "partials/helpdesk-chart/",
        views.HelpdeskChartPartialView.as_view(),
        name="partial-helpdesk-chart",
    ),
    path(
        "partials/incidents/",
        views.IncidentsPartialView.as_view(),
        name="partial-incidents",
    ),
    # Chart data API
    path("api/helpdesk-data/", views.helpdesk_chart_data, name="api-helpdesk-data"),
    # Documentation
    path("docs/", views.DocsIndexView.as_view(), name="docs-index"),
    path("docs/<slug:slug>/", views.DocsPageView.as_view(), name="docs-page"),
]
