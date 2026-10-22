"""URL configuration for the CVE section, mounted at /cves/."""

from django.urls import path

from . import views

app_name = "cves"

urlpatterns = [
    path("", views.cve_list, name="list"),
    path("new/", views.CVECreateView.as_view(), name="create"),
    path("<int:pk>/", views.CVEDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.CVEUpdateView.as_view(), name="edit"),
    path("<int:pk>/state/", views.set_state, name="state"),
    path("<int:pk>/links/", views.link_create, name="link-create"),
    path("<int:pk>/links/<int:link_pk>/delete/", views.link_delete, name="link-delete"),
    path("<int:pk>/comments/", views.comment_create, name="comment-create"),
    path("<int:pk>/attachments/", views.attachment_create, name="attachment-create"),
    path("<int:pk>/attachments/<str:key>/", views.attachment_view, name="attachment"),
    path("<int:pk>/attachments/<str:key>/delete/", views.attachment_delete, name="attachment-delete"),
]
