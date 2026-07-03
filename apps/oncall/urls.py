"""URL configuration for the on-call duty application."""

from django.urls import path

from . import views

app_name = "oncall"

urlpatterns = [
    path("", views.OnCallCalendarView.as_view(), name="calendar"),
    path("<int:year>/<int:week>/status/", views.oncall_week_status, name="week-status"),
    path("<int:year>/<int:week>/claim/", views.oncall_claim, name="claim"),
    path("<int:year>/<int:week>/release/", views.oncall_release, name="release"),
    path("<int:year>/<int:week>/assign/form/", views.oncall_assign_form, name="assign-form"),
    path("<int:year>/<int:week>/assign/", views.oncall_assign, name="assign"),
    path("<int:year>/<int:week>/history/", views.oncall_history, name="history"),
]
