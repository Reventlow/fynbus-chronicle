"""URLs for the ServiceDesk page (mounted at /servicedesk/)."""

from django.urls import path

from . import views

app_name = "servicedesk"

urlpatterns = [
    path("", views.tickets, name="tickets"),
    path("ticket/<int:sdp_id>/link/", views.link, name="link"),
    path("link/<int:pk>/unlink/", views.unlink, name="unlink"),
    path("link/<int:pk>/note/", views.retry_note, name="retry-note"),
]
