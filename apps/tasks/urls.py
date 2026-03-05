"""
URL configuration for the tasks application.
"""

from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.TaskListView.as_view(), name="task-list"),
    path("create/", views.TaskCreateView.as_view(), name="task-create"),
    path("<int:pk>/", views.TaskDetailView.as_view(), name="task-detail"),
    path("<int:pk>/edit/", views.TaskUpdateView.as_view(), name="task-edit"),
    path("<int:pk>/status/", views.task_change_status, name="task-status"),
    path("<int:pk>/notes/create/", views.task_note_create, name="task-note-create"),
    path(
        "<int:pk>/notes/<int:note_pk>/delete/",
        views.task_note_delete,
        name="task-note-delete",
    ),
    path("partials/row/<int:pk>/", views.task_row, name="task-row"),
    path("partials/list/", views.task_list_partial, name="task-list-partial"),
    path("api/chart-data/", views.task_chart_data, name="api-chart-data"),
]
