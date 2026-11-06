"""Microsoft Graph for the Planner board. **Sync container only.**

* :class:`PlannerAuth` holds the service account's tokens (MSAL, with the
  token cache kept sealed in :class:`~apps.planner.models.PlannerConnection`)
  and redeems a sign-in handed over by the web container.
* :class:`GraphClient` makes the read calls, follows paging and waits out
  Graph's throttling (429/503 with ``Retry-After``).

Nothing here logs or stores a token, a code or the client secret; error
messages carry Graph's error code and HTTP status only.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator

import msal
import requests
from django.conf import settings
from django.utils import timezone

from . import crypto
from .models import PendingSignIn, PlannerConnection

logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
# Delegated permissions consented on the "Chronicle Planner" app. MSAL adds
# openid/profile/offline_access itself. Phase 1 only reads; writes come with
# the per-user connections in a later release.
SCOPES = ["Tasks.ReadWrite", "User.ReadBasic.All"]


class PlannerError(Exception):
    """A failure worth showing on the board (no secrets in the message)."""


def authority() -> str:
    return f"https://login.microsoftonline.com/{settings.PLANNER_TENANT_ID}"


def authorize_url(*, state: str, code_challenge: str, redirect_uri: str) -> str:
    """Microsoft's sign-in URL for the service account (built in the web
    container, which needs only the client id, never the secret)."""
    from urllib.parse import urlencode

    params = {
        "client_id": settings.PLANNER_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": " ".join(["openid", "profile", "offline_access", *SCOPES]),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    if settings.PLANNER_SERVICE_ACCOUNT:
        params["login_hint"] = settings.PLANNER_SERVICE_ACCOUNT
    return f"{authority()}/oauth2/v2.0/authorize?{urlencode(params)}"


class PlannerAuth:
    """MSAL around the sealed token cache of the one connected account."""

    def __init__(self, connection: PlannerConnection | None = None, app_factory=None):
        if not settings.PLANNER_CLIENT_SECRET or not crypto.can_open():
            raise PlannerError("Sync-containeren mangler PLANNER_CLIENT_SECRET eller PLANNER_PRIVATE_KEY.")
        self.connection = connection or PlannerConnection.get()
        self.cache = msal.SerializableTokenCache()
        if self.connection.sealed_token_cache:
            self.cache.deserialize(crypto.open_sealed(self.connection.sealed_token_cache, as_json=False))
        factory = app_factory or msal.ConfidentialClientApplication
        self.app = factory(
            settings.PLANNER_CLIENT_ID,
            client_credential=settings.PLANNER_CLIENT_SECRET,
            authority=authority(),
            token_cache=self.cache,
        )

    def _save(self) -> None:
        if self.cache.has_state_changed:
            self.connection.sealed_token_cache = crypto.seal(self.cache.serialize())
            self.connection.save(update_fields=["sealed_token_cache"])

    def access_token(self) -> str:
        """A valid access token, refreshed through the cache when needed."""
        if not self.connection.is_connected:
            raise PlannerError("Planner er ikke forbundet. En administrator skal forbinde servicekontoen.")
        account = next((a for a in self.app.get_accounts()
                        if a.get("home_account_id") == self.connection.home_account_id), None)
        result = self.app.acquire_token_silent(SCOPES, account=account) if account else None
        self._save()
        if not result or "access_token" not in result:
            code = (result or {}).get("error", "no_account")
            self.connection.last_error = f"Login udløbet eller tilbagekaldt ({code}). Forbind Planner igen."
            self.connection.save(update_fields=["last_error"])
            raise PlannerError(self.connection.last_error)
        self.connection.last_token_ok_at = timezone.now()
        self.connection.last_error = ""
        self.connection.save(update_fields=["last_token_ok_at", "last_error"])
        return result["access_token"]

    def redeem(self, pending: PendingSignIn) -> None:
        """Turn a handed-over sign-in into a stored connection, or refuse it."""
        try:
            if pending.is_expired:
                raise PlannerError("Login-koden udløb, før den blev brugt. Prøv igen.")
            data = crypto.open_sealed(pending.sealed)
            result = self.app.acquire_token_by_authorization_code(
                data["code"], scopes=SCOPES, redirect_uri=data["redirect_uri"],
                data={"code_verifier": data["code_verifier"]},
            )
            if "access_token" not in result:
                raise PlannerError(f"Microsoft afviste login ({result.get('error', 'ukendt fejl')}).")
            claims = result.get("id_token_claims") or {}
            if claims.get("tid", "").lower() != settings.PLANNER_TENANT_ID.lower():
                raise PlannerError("Kontoen hører ikke til FynBus' tenant.")
            # Compared case-insensitively (SVC-… vs svc-…), stored as Entra has it.
            upn = claims.get("preferred_username") or ""
            expected = settings.PLANNER_SERVICE_ACCOUNT
            if expected and upn.lower() != expected.lower():
                raise PlannerError(f"Forkert konto: {upn or 'ukendt'}. Log ind som {expected}.")
            account = next((a for a in self.app.get_accounts()
                            if (a.get("local_account_id") or "") == claims.get("oid")), None)
            if account is None:
                raise PlannerError("Microsoft returnerede ingen konto.")
            # Only this account's tokens are kept.
            for other in self.app.get_accounts():
                if other is not account and other.get("home_account_id") != account["home_account_id"]:
                    self.app.remove_account(other)
            conn = self.connection
            conn.account_upn = upn
            conn.account_oid = claims.get("oid", "")
            conn.home_account_id = account["home_account_id"]
            conn.connected_at = timezone.now()
            conn.connected_by = pending.created_by
            conn.last_token_ok_at = timezone.now()
            conn.last_error = ""
            conn.sealed_token_cache = crypto.seal(self.cache.serialize())
            conn.save()
            pending.status = PendingSignIn.Status.DONE
            pending.message = f"Forbundet som {upn}."
            logger.info("Planner connected as %s", upn)
        except PlannerError as exc:
            pending.status = PendingSignIn.Status.FAILED
            pending.message = str(exc)[:500]
            logger.warning("Planner sign-in refused: %s", exc)
        except Exception:
            pending.status = PendingSignIn.Status.FAILED
            pending.message = "Uventet fejl under login. Se sync-containerens log."
            logger.exception("Planner sign-in failed")
        finally:
            pending.sealed = ""  # the code is single-use; never keep it
            pending.handled_at = timezone.now()
            pending.save()


class GraphClient:
    """Read-only Graph calls with paging and throttling."""

    MAX_RETRIES = 4

    def __init__(self, token: Callable[[], str], session: requests.Session | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self._token = token
        self.session = session or requests.Session()
        self.sleep = sleep

    def get(self, path: str, params: dict | None = None) -> dict:
        url = path if path.startswith("https://") else f"{GRAPH}{path}"
        for attempt in range(self.MAX_RETRIES + 1):
            resp = self.session.get(url, params=params, timeout=30,
                                    headers={"Authorization": f"Bearer {self._token()}"})
            if resp.status_code in (429, 503, 504) and attempt < self.MAX_RETRIES:
                wait = float(resp.headers.get("Retry-After") or 2 ** attempt)
                logger.info("Graph throttled (%s), waiting %.0fs", resp.status_code, wait)
                self.sleep(min(wait, 120))
                continue
            if resp.status_code >= 400:
                try:
                    err = resp.json().get("error", {}).get("code", "")
                except ValueError:
                    err = ""
                raise PlannerError(f"Microsoft Graph svarede {resp.status_code} {err} på {path.split('?')[0]}".strip())
            return resp.json()
        raise PlannerError(f"Microsoft Graph blev ved med at bremse kaldet til {path}.")

    def get_all(self, path: str, params: dict | None = None) -> Iterator[dict]:
        """Every item across @odata.nextLink pages."""
        page = self.get(path, params)
        while True:
            yield from page.get("value", [])
            nxt = page.get("@odata.nextLink")
            if not nxt:
                return
            page = self.get(nxt)
