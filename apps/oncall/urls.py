"""URL configuration for the on-call duty application."""

from django.urls import path

from . import views

app_name = "oncall"

urlpatterns = [
    path("", views.OnCallCalendarView.as_view(), name="calendar"),
    path("<int:year>/<int:week>/claim/", views.oncall_claim, name="claim"),
    path("<int:year>/<int:week>/release/", views.oncall_release, name="release"),
]
