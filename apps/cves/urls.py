"""URL configuration for the CVE section, mounted at /cves/."""

from django.urls import path

from . import views

app_name = "cves"

CASE = {"kind": "case"}

urlpatterns = [
    path("", views.cve_list, name="list"),
    path("new/", views.CVECreateView.as_view(), name="create"),
    path("<int:pk>/", views.CVEDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.CVEUpdateView.as_view(), name="edit"),
    path("<int:pk>/state/", views.set_state, name="state"),
    path("<int:pk>/links/", views.link_create, name="link-create"),
    path("<int:pk>/links/<int:link_pk>/delete/", views.link_delete, name="link-delete"),
    path("<int:pk>/comments/", views.comment_create, name="comment-create"),
    path("<int:pk>/comments/<int:comment_pk>/", views.comment_row, name="comment"),
    path("<int:pk>/comments/<int:comment_pk>/edit/", views.comment_edit, name="comment-edit"),
    path("<int:pk>/attachments/", views.attachment_create, name="attachment-create"),
    path("<int:pk>/attachments/<str:key>/", views.attachment_view, name="attachment"),
    path("<int:pk>/attachments/<str:key>/delete/", views.attachment_delete, name="attachment-delete"),
    path("<int:pk>/attachments/<str:key>/preview/", views.attachment_preview, name="attachment-preview"),
    path("<int:pk>/case/", views.cve_join_case, name="join-case"),
    # Cases. Links, comments and attachments reuse the CVE views with kind="case".
    path("cases/", views.case_list, name="case-list"),
    path("cases/new/", views.CVECaseCreateView.as_view(), name="case-create"),
    path("cases/<int:pk>/", views.CVECaseDetailView.as_view(), name="case-detail"),
    path("cases/<int:pk>/edit/", views.CVECaseUpdateView.as_view(), name="case-edit"),
    path("cases/<int:pk>/state/", views.case_state, name="case-state"),
    path("cases/<int:pk>/export/<str:section>/", views.case_export_toggle, name="case-export-toggle"),
    path("cases/<int:pk>/cves/", views.case_add_cves, name="case-add-cves"),
    path("cases/<int:pk>/cves/<int:cve_pk>/remove/", views.case_remove_cve, name="case-remove-cve"),
    path("cases/<int:pk>/links/", views.link_create, CASE, name="case-link-create"),
    path("cases/<int:pk>/links/<int:link_pk>/delete/", views.link_delete, CASE, name="case-link-delete"),
    path("cases/<int:pk>/comments/", views.comment_create, CASE, name="case-comment-create"),
    path("cases/<int:pk>/comments/<int:comment_pk>/", views.comment_row, CASE, name="case-comment"),
    path("cases/<int:pk>/comments/<int:comment_pk>/edit/", views.comment_edit, CASE, name="case-comment-edit"),
    path("cases/<int:pk>/attachments/", views.attachment_create, CASE, name="case-attachment-create"),
    path("cases/<int:pk>/attachments/<str:key>/", views.attachment_view, CASE, name="case-attachment"),
    path("cases/<int:pk>/attachments/<str:key>/delete/", views.attachment_delete, CASE, name="case-attachment-delete"),
    path("cases/<int:pk>/attachments/<str:key>/preview/", views.attachment_preview, CASE, name="case-attachment-preview"),
]
