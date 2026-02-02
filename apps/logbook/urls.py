"""URL configuration for the logbook application."""

from django.urls import path

from . import views

app_name = "logbook"

urlpatterns = [
    # Week log views
    path("", views.WeekLogListView.as_view(), name="weeklog-list"),
    path("<int:pk>/", views.WeekLogDetailView.as_view(), name="weeklog-detail"),
    path("create/", views.WeekLogCreateView.as_view(), name="weeklog-create"),
    path("<int:pk>/edit/", views.WeekLogUpdateView.as_view(), name="weeklog-edit"),
    # HTMX partials for priority items
    path(
        "priority-item/new/",
        views.PriorityItemCreateView.as_view(),
        name="priority-item-create",
    ),
    path(
        "priority-item/<int:pk>/edit/",
        views.PriorityItemUpdateView.as_view(),
        name="priority-item-edit",
    ),
    path(
        "priority-item/<int:pk>/delete/",
        views.PriorityItemDeleteView.as_view(),
        name="priority-item-delete",
    ),
    path(
        "priority-item/<int:pk>/row/",
        views.priority_item_row,
        name="priority-item-row",
    ),
    # HTMX partials for absences
    path("absence/new/", views.AbsenceCreateView.as_view(), name="absence-create"),
    path(
        "absence/<int:pk>/edit/",
        views.AbsenceUpdateView.as_view(),
        name="absence-edit",
    ),
    path(
        "absence/<int:pk>/delete/",
        views.AbsenceDeleteView.as_view(),
        name="absence-delete",
    ),
    path(
        "absence/<int:pk>/row/",
        views.absence_row,
        name="absence-row",
    ),
    # HTMX partials for incidents
    path("incident/new/", views.IncidentCreateView.as_view(), name="incident-create"),
    path(
        "incident/<int:pk>/edit/",
        views.IncidentUpdateView.as_view(),
        name="incident-edit",
    ),
    path(
        "incident/<int:pk>/delete/",
        views.IncidentDeleteView.as_view(),
        name="incident-delete",
    ),
    path(
        "incident/<int:pk>/row/",
        views.incident_row,
        name="incident-row",
    ),
    # Export endpoints
    path("<int:pk>/export/pdf/", views.export_pdf, name="export-pdf"),
    path("<int:pk>/export/markdown/", views.export_markdown, name="export-markdown"),
    path("<int:pk>/export/email/", views.export_email, name="export-email"),
]
