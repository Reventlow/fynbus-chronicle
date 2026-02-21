"""
Microsoft Graph API email backend for Django.

Sends email via the Microsoft Graph sendMail endpoint using OAuth2
client credentials flow. Reuses the Azure AD app registration already
configured for SSO (MICROSOFT_CLIENT_ID / SECRET / TENANT_ID).

Requires the Mail.Send *application* permission granted in Azure.
"""

import base64
import logging
import threading
import time

import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

# Module-level token cache (shared across send calls within the process).
_token_lock = threading.Lock()
_cached_token: str | None = None
_token_expires_at: float = 0.0


def _get_access_token() -> str:
    """
    Acquire an OAuth2 access token via client credentials grant.

    Tokens are cached at module level and refreshed 5 minutes before expiry.
    """
    global _cached_token, _token_expires_at

    with _token_lock:
        # Return cached token if still valid (with 5 min buffer).
        if _cached_token and time.time() < (_token_expires_at - 300):
            return _cached_token

        tenant_id = settings.MICROSOFT_TENANT_ID
        client_id = settings.MICROSOFT_CLIENT_ID
        client_secret = settings.MICROSOFT_CLIENT_SECRET

        token_url = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        )
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        response = requests.post(token_url, data=data, timeout=30)
        response.raise_for_status()

        token_data = response.json()
        _cached_token = token_data["access_token"]
        _token_expires_at = time.time() + token_data.get("expires_in", 3599)

        logger.debug("Acquired new Graph API access token")
        return _cached_token


def _build_recipient(email: str) -> dict:
    """Build a Graph API recipient object from an email address."""
    return {"emailAddress": {"address": email}}


def _build_message_payload(message: EmailMessage) -> dict:
    """
    Convert a Django EmailMessage into a Graph API sendMail payload.

    Handles HTML/plain text bodies, CC/BCC, and file attachments.
    """
    # Determine content type.
    content_type = getattr(message, "content_subtype", "plain")
    graph_content_type = "HTML" if content_type == "html" else "Text"

    payload: dict = {
        "message": {
            "subject": message.subject,
            "body": {
                "contentType": graph_content_type,
                "content": message.body,
            },
            "toRecipients": [_build_recipient(addr) for addr in message.to],
        },
        "saveToSentItems": True,
    }

    msg = payload["message"]

    if message.cc:
        msg["ccRecipients"] = [_build_recipient(addr) for addr in message.cc]

    if message.bcc:
        msg["bccRecipients"] = [
            _build_recipient(addr) for addr in message.bcc
        ]

    # Handle attachments.
    if message.attachments:
        msg["attachments"] = []
        for attachment in message.attachments:
            if isinstance(attachment, tuple):
                filename, content, mimetype = attachment
                if isinstance(content, str):
                    content = content.encode("utf-8")
                msg["attachments"].append(
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": filename,
                        "contentType": mimetype or "application/octet-stream",
                        "contentBytes": base64.b64encode(content).decode(
                            "ascii"
                        ),
                    }
                )

    return payload


class GraphEmailBackend(BaseEmailBackend):
    """
    Django email backend that sends via Microsoft Graph API.

    Uses client credentials OAuth2 flow with the existing Azure AD
    app registration. The sender (from_email) must be a valid mailbox
    in the tenant with Mail.Send permission granted.
    """

    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        """
        Send one or more EmailMessage objects via Graph API.

        Returns the number of messages sent successfully.
        """
        if not email_messages:
            return 0

        sent_count = 0

        try:
            token = _get_access_token()
        except Exception:
            logger.exception("Failed to acquire Graph API access token")
            if not self.fail_silently:
                raise
            return 0

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        for message in email_messages:
            try:
                from_email = message.from_email or settings.DEFAULT_FROM_EMAIL
                url = (
                    f"https://graph.microsoft.com/v1.0"
                    f"/users/{from_email}/sendMail"
                )

                payload = _build_message_payload(message)

                response = requests.post(
                    url, json=payload, headers=headers, timeout=30
                )
                response.raise_for_status()

                sent_count += 1
                logger.info(
                    "Email sent via Graph API from=%s to=%s subject='%s'",
                    from_email,
                    message.to,
                    message.subject,
                )
            except Exception:
                logger.exception(
                    "Failed to send email via Graph API to=%s subject='%s'",
                    message.to,
                    message.subject,
                )
                if not self.fail_silently:
                    raise

        return sent_count
