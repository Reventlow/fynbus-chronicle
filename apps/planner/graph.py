"""Microsoft Graph for the Planner board. **Sync container only.**

* :class:`PlannerAuth` holds one account's tokens (MSAL, with the token
  cache kept sealed in :class:`~apps.planner.models.PlannerConnection` for
  the service account or :class:`~apps.planner.models.PlannerUserConnection`
  for an editor) and redeems a sign-in handed over by the web container.
* :class:`GraphClient` makes the calls, follows paging, waits out Graph's
  throttling (429/503 with ``Retry-After``) and sends Planner's ``If-Match``
  etags on writes.

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
from .models import PendingSignIn, PlannerConnection, PlannerUserConnection

logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
# Delegated permissions consented on the "Chronicle Planner" app. MSAL adds
# openid/profile/offline_access itself. The service account only reads;
# editors' own connections write.
SCOPES = ["Tasks.ReadWrite", "User.ReadBasic.All"]


class PlannerError(Exception):
    """A failure worth showing on the board (no secrets in the message)."""


class GraphError(PlannerError):
    """Graph answered with an error status; keeps it for callers to react to."""

    def __init__(self, status: int, code: str, path: str):
        self.status, self.code = status, code
        super().__init__(f"Microsoft Graph svarede {status} {code} på {path}".strip())


def authority() -> str:
    return f"https://login.microsoftonline.com/{settings.PLANNER_TENANT_ID}"


def authorize_url(*, state: str, code_challenge: str, redirect_uri: str, login_hint: str | None = None) -> str:
    """Microsoft's sign-in URL (built in the web container, which needs only
    the client id, never the secret). Without ``login_hint`` it is the
    service account's sign-in."""
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
    }
    if login_hint is None:
        # The service account: make the person pick it, not their own.
        params["prompt"] = "select_account"
        login_hint = settings.PLANNER_SERVICE_ACCOUNT
    if login_hint:
        params["login_hint"] = login_hint
    return f"{authority()}/oauth2/v2.0/authorize?{urlencode(params)}"


def _expected_identity(user) -> tuple[str, str]:
    """(Entra object id, e-mail) an editor's own sign-in must match.

    The object id comes from their Microsoft SSO link, if they have one;
    otherwise their e-mail address in Chronicle has to match the UPN.
    """
    from allauth.socialaccount.models import SocialAccount

    social = SocialAccount.objects.filter(user=user, provider="microsoft").first()
    return (social.uid if social else ""), (user.email or "")


class PlannerAuth:
    """MSAL around the sealed token cache of one connected account: the
    service account (default) or an editor's own (:meth:`for_user`)."""

    def __init__(self, connection: PlannerConnection | PlannerUserConnection | None = None, app_factory=None):
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

    @classmethod
    def for_user(cls, user, **kwargs) -> PlannerAuth:
        """The editor's own connection; never the service account."""
        conn = PlannerUserConnection.objects.filter(user=user).first()
        if conn is None or not conn.is_connected:
            raise PlannerError("Din Microsoft-konto er ikke forbundet til Planner. Forbind den på Planner-siden.")
        return cls(connection=conn, **kwargs)

    @property
    def is_personal(self) -> bool:
        return isinstance(self.connection, PlannerUserConnection)

    def _save(self) -> None:
        if self.cache.has_state_changed:
            self.connection.sealed_token_cache = crypto.seal(self.cache.serialize())
            self.connection.save(update_fields=["sealed_token_cache"])

    def access_token(self) -> str:
        """A valid access token, refreshed through the cache when needed."""
        if not self.connection.is_connected:
            if self.is_personal:
                raise PlannerError("Din Microsoft-konto er ikke forbundet til Planner.")
            raise PlannerError("Planner er ikke forbundet. En administrator skal forbinde servicekontoen.")
        account = next((a for a in self.app.get_accounts()
                        if a.get("home_account_id") == self.connection.home_account_id), None)
        result = self.app.acquire_token_silent(SCOPES, account=account) if account else None
        self._save()
        if not result or "access_token" not in result:
            code = (result or {}).get("error", "no_account")
            again = "Forbind din konto igen." if self.is_personal else "Forbind Planner igen."
            self.connection.last_error = f"Login udløbet eller tilbagekaldt ({code}). {again}"
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
            if pending.for_user_id:
                self._check_personal(pending.for_user, upn, claims.get("oid", ""))
            else:
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
            if not self.is_personal:
                conn.connected_by = pending.created_by
            conn.last_token_ok_at = timezone.now()
            conn.last_error = ""
            conn.sealed_token_cache = crypto.seal(self.cache.serialize())
            conn.save()
            pending.status = PendingSignIn.Status.DONE
            pending.message = f"Forbundet som {upn}."
            logger.info("Planner connected as %s%s", upn, " (personal)" if self.is_personal else "")
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


    @staticmethod
    def _check_personal(user, upn: str, oid: str) -> None:
        """An editor may connect only their own account, never the service
        account (its changes would carry the wrong name)."""
        if settings.PLANNER_SERVICE_ACCOUNT and upn.lower() == settings.PLANNER_SERVICE_ACCOUNT.lower():
            raise PlannerError("Servicekontoen kan ikke bruges som din personlige forbindelse. Log ind med din egen konto.")
        expected_oid, expected_email = _expected_identity(user)
        if expected_oid:
            if oid.lower() != expected_oid.lower():
                raise PlannerError(f"Forkert konto: {upn or 'ukendt'}. Log ind med den konto, du bruger til Chronicle.")
        elif not expected_email or upn.lower() != expected_email.lower():
            raise PlannerError(f"Forkert konto: {upn or 'ukendt'}. Log ind med {expected_email or 'din egen konto'}.")


class GraphClient:
    """Graph calls with paging, throttling and Planner's etags."""

    MAX_RETRIES = 4

    def __init__(self, token: Callable[[], str], session: requests.Session | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self._token = token
        self.session = session or requests.Session()
        self.sleep = sleep

    def get(self, path: str, params: dict | None = None) -> dict:
        return self.request("GET", path, params=params)

    def patch(self, path: str, body: dict, etag: str) -> dict:
        """Planner refuses an update without the item's current etag. Asks
        for the updated item back; ``{}`` if Graph sends none."""
        return self.request("PATCH", path, json=body,
                            headers={"If-Match": etag, "Prefer": "return=representation"})

    def post(self, path: str, body: dict) -> dict:
        return self.request("POST", path, json=body)

    def request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None,
                headers: dict | None = None) -> dict:
        url = path if path.startswith("https://") else f"{GRAPH}{path}"
        for attempt in range(self.MAX_RETRIES + 1):
            send = {"Authorization": f"Bearer {self._token()}", **(headers or {})}
            if method == "GET":
                resp = self.session.get(url, params=params, timeout=30, headers=send)
            else:
                resp = self.session.request(method, url, params=params, json=json, timeout=30, headers=send)
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
                raise GraphError(resp.status_code, err, path.split("?")[0])
            if resp.status_code == 204:
                return {}
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
