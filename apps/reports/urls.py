"""URL configuration for reports.

``/reports/`` and ``/reports/<slug>/`` require login; ``/reports/p/<token>/``
is the public link and deliberately sits outside the login requirement.
"""

from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_list, name="list"),
    path("upload/", views.report_upload, name="upload"),
    path("p/<str:token>/", views.report_public, name="public"),
    path("p/<str:token>/video/", views.report_public_video, name="public-video"),
    path("<slug:slug>/", views.report_view, name="view"),
    path("<slug:slug>/video/", views.report_video, name="video"),
    path("<slug:slug>/visibility/", views.report_visibility, name="visibility"),
    path("<slug:slug>/rotate/", views.report_rotate, name="rotate"),
    path("<slug:slug>/delete/", views.report_delete, name="delete"),
]
