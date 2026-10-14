"""Pasted images in incident descriptions (0.19.1): pasteable in the form,
shown on the week log, and carried into the PDF, HTML and email exports —
which cannot fetch the login-gated /images/ URL, so the bytes travel along.
"""

import base64
import io
import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.images.embedding import embed_as_cid, embed_as_data_uris
from apps.images.models import PastedImage
from apps.logbook.exports.email import send_weeklog_email
from apps.logbook.exports.html import generate_html
from apps.logbook.exports.pdf import generate_pdf
from apps.logbook.forms import IncidentForm
from apps.logbook.models import Incident, WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def image_dir(settings, tmp_path):
    settings.IMAGE_FILES_DIR = tmp_path / "images"


def _image(width=1200, height=600) -> PastedImage:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buf, "PNG")
    image = PastedImage(content_type="image/png", width=width, height=height, created_at=timezone.now())
    image.file.save("pasted", ContentFile(buf.getvalue()), save=False)
    image.save()
    return image


@pytest.fixture
def image():
    return _image()


@pytest.fixture
def weeklog(settings, image):
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["team@fynbus.dk"]
    weeklog = WeekLog.objects.create(year=2026, week_number=42)
    Incident.objects.create(
        weeklog=weeklog,
        title="Printer-nedbrud",
        description=f"Fejlbesked:\n\n![billede|480](/images/{image.key}/)",
    )
    return weeklog


# --- form and week log page ---------------------------------------------------------


def test_incident_form_accepts_pasted_images():
    assert "data-paste-images" in str(IncidentForm()["description"])


def test_week_log_shows_the_image(client, weeklog, image):
    client.force_login(User.objects.create_user("gre", password="x"))
    body = client.get(reverse("logbook:weeklog-detail", kwargs={"year": 2026, "week": 42})).content.decode()
    assert f'src="/images/{image.key}/" width="480"' in body


# --- embedding helper -----------------------------------------------------------------


def test_data_uri_carries_the_bytes_and_a_capped_size(image):
    html = f'<p><img alt="billede" src="/images/{image.key}/"></p>'
    out = embed_as_data_uris(html, max_width=640)
    assert "/images/" not in out
    src = re.search(r'src="data:image/png;base64,([^"]+)"', out).group(1)
    assert base64.b64decode(src).startswith(b"\x89PNG")
    # 1200×600 natural size, capped to 640 wide, height kept in proportion.
    assert 'width="640" height="320"' in out
    # WeasyPrint ignores the attributes, so the size is repeated as a style.
    assert 'style="width: 640px; height: 320px;"' in out


def test_requested_width_is_kept_when_it_fits(image):
    out = embed_as_data_uris(f'<img alt="billede" src="/images/{image.key}/" width="300">', max_width=640)
    assert 'width="300" height="150"' in out and out.count("width=") == 1


def test_missing_image_is_dropped():
    out = embed_as_data_uris('<p>før <img alt="billede" src="/images/' + "0" * 32 + '/"> efter</p>', max_width=640)
    assert out == "<p>før  efter</p>"


def test_cid_embedding_attaches_each_image_once(image):
    html = f'<img src="/images/{image.key}/"><img src="/images/{image.key}/">'
    out, parts = embed_as_cid(html, max_width=600)
    assert len(parts) == 1
    assert out.count(f'src="cid:{parts[0].cid}"') == 2
    assert parts[0].subtype == "png" and parts[0].data.startswith(b"\x89PNG")


def test_other_images_are_left_alone():
    html = '<img src="https://example.com/x.png"><img src="cid:chart">'
    assert embed_as_data_uris(html, max_width=640) == html


# --- exports ---------------------------------------------------------------------------


def test_pdf_embeds_the_image(weeklog, image):
    pdf = generate_pdf(weeklog)
    assert pdf.startswith(b"%PDF")
    # An embedded raster image shows up as an image XObject.
    assert b"/Subtype /Image" in pdf


def test_html_export_is_self_contained(weeklog, image):
    html = generate_html(weeklog)
    assert f"/images/{image.key}/" not in html
    assert 'src="data:image/png;base64,' in html
    assert 'width="480" height="240"' in html


def test_email_attaches_the_image_inline(weeklog, image):
    ok, message = send_weeklog_email(weeklog, format="html", from_email="gorm@fynbus.dk")
    assert ok, message
    sent = mail.outbox[0]
    cid = f"chronicle-image-{image.key}"
    assert f'src="cid:{cid}" width="480" height="240"' in sent.body
    assert 'src="data:' not in sent.body  # Outlook classic refuses these
    attached = {a.get("Content-ID").strip("<>"): a for a in sent.attachments if not isinstance(a, tuple)}
    assert attached[cid].get_content_type() == "image/png"


def test_email_shows_the_full_description(weeklog):
    weeklog.incidents.update(description=" ".join(["ord"] * 60) + " SLUT")
    send_weeklog_email(weeklog, format="html", from_email="gorm@fynbus.dk")
    assert "SLUT" in mail.outbox[0].body
