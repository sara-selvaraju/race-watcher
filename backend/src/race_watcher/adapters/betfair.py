from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.domain.models import DomainMeeting, DomainPrice

log = get_logger("betfair")

IDENTITY_SSO_AU = "https://identitysso.betfair.com.au/api/login"
IDENTITY_CERTLOGIN = "https://identitysso-cert.betfair.com.au/api/certlogin"
API_NG = "https://api.betfair.com.au/exchange/betting/json-rpc/v1"

EVENT_TYPE_HORSE_RACING = "7"
MARKET_TYPE_WIN = "WIN"
COUNTRY_AU = "AU"


class BetfairAdapter:
    """Thin Betfair Exchange API client.

    Two login modes:
    - **certlogin** (preferred for headless deploys): non-interactive, uses a client cert+key.
    - **interactive login**: username/password only — fine for local dev.

    Live odds are pulled via `listMarketBook` for the WIN markets discovered by `listMarketCatalogue`
    on race day. Runner ↔ selection mapping is cached on the `runner.betfair_selection_id` column
    by the worker on the first poll.
    """

    name = "betfair"

    def __init__(self, *, http: httpx.Client | None = None):
        self._http = http or httpx.Client(timeout=15.0)
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    # ---- auth -------------------------------------------------------------

    def _login(self) -> str:
        if not (settings.betfair_app_key and settings.betfair_username and settings.betfair_password):
            raise RuntimeError("Betfair credentials are not configured")

        if settings.betfair_cert_path and settings.betfair_cert_key_path:
            r = self._http.post(
                IDENTITY_CERTLOGIN,
                data={
                    "username": settings.betfair_username,
                    "password": settings.betfair_password,
                },
                headers={
                    "X-Application": settings.betfair_app_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                cert=(settings.betfair_cert_path, settings.betfair_cert_key_path),
            )
            r.raise_for_status()
            body = r.json()
            if body.get("loginStatus") != "SUCCESS":
                raise RuntimeError(f"Betfair certlogin failed: {body.get('loginStatus')}")
            return body["sessionToken"]

        r = self._http.post(
            IDENTITY_SSO_AU,
            data={"username": settings.betfair_username, "password": settings.betfair_password},
            headers={"X-Application": settings.betfair_app_key},
        )
        r.raise_for_status()
        body = r.json()
        if body.get("status") != "SUCCESS":
            raise RuntimeError(f"Betfair interactive login failed: {body.get('status')}")
        return body["token"]

    def _session_token(self) -> str:
        if self._token and self._token_expires_at and datetime.now(UTC) < self._token_expires_at:
            return self._token
        self._token = self._login()
        # Betfair sessions live ~4h on interactive, ~24h on certlogin; refresh well before.
        self._token_expires_at = datetime.now(UTC) + timedelta(hours=3)
        return self._token

    # ---- JSON-RPC ---------------------------------------------------------

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _rpc(self, method: str, params: dict) -> list | dict:
        headers = {
            "X-Application": settings.betfair_app_key or "",
            "X-Authentication": self._session_token(),
            "Content-Type": "application/json",
        }
        r = self._http.post(
            API_NG,
            json={"jsonrpc": "2.0", "method": f"SportsAPING/v1.0/{method}", "params": params, "id": 1},
            headers=headers,
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise RuntimeError(f"Betfair RPC error: {body['error']}")
        return body["result"]

    # ---- domain calls -----------------------------------------------------

    def list_meeting_markets(self, meeting: DomainMeeting) -> list[dict]:
        """Return WIN markets at the meeting's track on race date."""
        date_from = datetime.combine(meeting.date, datetime.min.time(), tzinfo=UTC)
        date_to = date_from + timedelta(days=1)
        result = self._rpc(
            "listMarketCatalogue",
            {
                "filter": {
                    "eventTypeIds": [EVENT_TYPE_HORSE_RACING],
                    "marketCountries": [COUNTRY_AU],
                    "marketTypeCodes": [MARKET_TYPE_WIN],
                    "venues": [meeting.track],
                    "marketStartTime": {
                        "from": date_from.isoformat().replace("+00:00", "Z"),
                        "to": date_to.isoformat().replace("+00:00", "Z"),
                    },
                },
                "marketProjection": ["RUNNER_METADATA", "MARKET_START_TIME", "EVENT"],
                "maxResults": 50,
                "sort": "FIRST_TO_START",
            },
        )
        return result  # type: ignore[return-value]

    def list_market_book(self, market_ids: list[str]) -> list[dict]:
        if not market_ids:
            return []
        return self._rpc(  # type: ignore[return-value]
            "listMarketBook",
            {
                "marketIds": market_ids,
                "priceProjection": {"priceData": ["EX_BEST_OFFERS"]},
            },
        )

    def fetch_prices(self, meeting: DomainMeeting) -> list[DomainPrice]:
        try:
            markets = self.list_meeting_markets(meeting)
        except Exception as exc:
            log.warning("betfair.list_markets_failed", error=str(exc))
            return []
        if not markets:
            return []

        # Map race number → marketId by matching market name "R{n}" (Betfair uses "R{n} ...").
        race_num_to_market: dict[int, str] = {}
        selection_to_runner: dict[tuple[str, int], tuple[int, int]] = {}  # (mid, selId) → (race#, runner#)
        for m in markets:
            mname = m.get("marketName", "")
            race_num = _race_number_from_market_name(mname)
            if race_num is None:
                continue
            race_num_to_market[race_num] = m["marketId"]
            race = next((r for r in meeting.races if r.number == race_num), None)
            if race is None:
                continue
            # Match runner selections by name (best-effort).
            for sel in m.get("runners", []):
                runner = _match_runner(sel.get("runnerName", ""), race.runners)
                if runner is None:
                    continue
                selection_to_runner[(m["marketId"], int(sel["selectionId"]))] = (
                    race_num,
                    runner.number,
                )

        try:
            books = self.list_market_book(list(race_num_to_market.values()))
        except Exception as exc:
            log.warning("betfair.list_book_failed", error=str(exc))
            return []

        now = datetime.now(UTC)
        prices: list[DomainPrice] = []
        for book in books:
            mid = book["marketId"]
            for r in book.get("runners", []):
                key = (mid, int(r["selectionId"]))
                mapping = selection_to_runner.get(key)
                if not mapping:
                    continue
                race_num, runner_num = mapping
                best = (r.get("ex") or {}).get("availableToBack") or []
                if not best:
                    continue
                price = Decimal(str(best[0]["price"]))
                prices.append(
                    DomainPrice(
                        race_number=race_num,
                        runner_number=runner_num,
                        price=price,
                        source="betfair",
                        taken_at=now,
                    )
                )
        return prices


def _race_number_from_market_name(name: str) -> int | None:
    # Betfair WIN markets are usually "R1 1400m Mdn" or similar.
    if not name or not name.startswith("R"):
        return None
    head = name.split(" ", 1)[0]
    digits = head.lstrip("R")
    return int(digits) if digits.isdigit() else None


def _match_runner(selection_name: str, runners):  # noqa: ANN001
    if not selection_name:
        return None
    norm = _normalise(selection_name)
    for runner in runners:
        if _normalise(runner.name) == norm:
            return runner
    return None


def _normalise(s: str) -> str:
    return "".join(c.lower() for c in s if c.isalnum())
