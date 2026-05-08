"""URLs for the themes management page."""

from django.urls import path

from . import views

app_name = "themes"

urlpatterns = [
    path("", views.manage, name="manage"),
    path("<int:theme_pk>/schedule/add/", views.schedule_create, name="schedule-create"),
    path("schedule/<int:schedule_pk>/delete/", views.schedule_delete, name="schedule-delete"),
]
