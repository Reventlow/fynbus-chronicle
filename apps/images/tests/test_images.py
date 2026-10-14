"""Pasted images: Ctrl+V into a task or feature-request description uploads
the image and inserts a Markdown reference that the detail pages render."""

import io

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.feedback.models import FeatureRequest
from apps.images.models import PastedImage
from apps.logbook.templatetags.markdown_extras import render_markdown, strip_images
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def image_dir(settings, tmp_path):
    settings.IMAGE_FILES_DIR = tmp_path / "images"
    return settings.IMAGE_FILES_DIR


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


@pytest.fixture
def viewer(client):
    user = User.objects.create_user("viewer", password="x")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(user)
    return user


def _png(width=4, height=3, fmt="PNG") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buf, fmt)
    return SimpleUploadedFile("image.png", buf.getvalue(), content_type="image/png")


def _upload(client, file):
    return client.post(reverse("images:upload"), {"image": file})


# --- upload --------------------------------------------------------------------


def test_upload_stores_image_and_returns_markdown(client, editor, image_dir):
    response = _upload(client, _png())
    assert response.status_code == 201
    data = response.json()
    image = PastedImage.objects.get()
    assert data["url"] == f"/images/{image.key}/"
    assert data["markdown"] == f"![billede](/images/{image.key}/)"
    assert (image.width, image.height) == (4, 3)
    assert image.uploaded_by == editor
    assert image.file.path.startswith(str(image_dir)) and image.file.path.endswith(".png")


def test_format_comes_from_the_bytes_not_the_name(client, editor):
    # A JPEG sent as "image.png" with image/png is stored and served as JPEG.
    _upload(client, _png(fmt="JPEG"))
    image = PastedImage.objects.get()
    assert image.content_type == "image/jpeg" and image.file.name.endswith(".jpg")


def test_non_image_is_rejected(client, editor):
    fake = SimpleUploadedFile("x.png", b"<script>alert(1)</script>", content_type="image/png")
    assert _upload(client, fake).status_code == 400
    assert not PastedImage.objects.exists()


def test_svg_is_rejected(client, editor):
    svg = SimpleUploadedFile("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>', content_type="image/svg+xml")
    assert _upload(client, svg).status_code == 400


def test_missing_file_is_rejected(client, editor):
    assert client.post(reverse("images:upload")).status_code == 400


def test_viewer_cannot_upload(client, viewer):
    assert _upload(client, _png()).status_code == 403


def test_anonymous_cannot_upload(client):
    assert _upload(client, _png()).status_code == 302
    assert not PastedImage.objects.exists()


# --- serving -------------------------------------------------------------------


def test_logged_in_users_can_view(client, editor, viewer):
    client.force_login(editor)  # the viewer fixture logged in last
    url = _upload(client, _png()).json()["url"]
    client.force_login(viewer)
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Cache-Control"].startswith("private")
    assert b"".join(response.streaming_content).startswith(b"\x89PNG")


def test_anonymous_cannot_view(client, editor):
    url = _upload(client, _png()).json()["url"]
    client.logout()
    assert client.get(url).status_code == 302


def test_unknown_key_is_404(client, editor):
    assert client.get(reverse("images:view", kwargs={"key": "0" * 32})).status_code == 404


# --- rendering -----------------------------------------------------------------


def test_markdown_renders_the_image():
    html = render_markdown("Se her:\n\n![billede](/images/abc123/)")
    assert '<img src="/images/abc123/" alt="billede"' in html or '<img alt="billede" src="/images/abc123/"' in html


def test_card_preview_strips_image_references():
    assert strip_images("Fejl ved login ![billede](/images/abc/) se ovenfor") == "Fejl ved login [billede] se ovenfor"


def test_task_detail_shows_pasted_image(client, editor):
    task = Task.objects.create(title="T", description="Skærmbillede:\n\n![billede](/images/abc/)")
    body = client.get(task.get_absolute_url()).content.decode()
    assert 'src="/images/abc/"' in body


def test_feature_request_detail_shows_pasted_image(client, editor):
    fr = FeatureRequest.objects.create(title="F", description="![billede](/images/abc/)")
    body = client.get(reverse("feedback:detail", kwargs={"pk": fr.pk})).content.decode()
    assert 'src="/images/abc/"' in body


def test_paste_handler_is_only_installed_for_editors(client, editor, viewer):
    client.force_login(editor)
    assert "data-paste-images" in client.get(reverse("tasks:task-create")).content.decode()
    assert "UPLOAD_URL" in client.get(reverse("tasks:task-list")).content.decode()
    client.force_login(viewer)
    assert "UPLOAD_URL" not in client.get(reverse("tasks:task-list")).content.decode()
