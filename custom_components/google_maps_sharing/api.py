"""Client sincrono per la condivisione posizione di Google Maps.

La richiesta e il parsing riprendono locationsharinglib (MIT, Costas Tyfoxylos);
in più il client legge i cookie #HttpOnly_, usa un timeout, rileva la sessione
scaduta a ogni lettura e salva su file i cookie rinnovati da Google.
"""

from __future__ import annotations

import json
import logging
import os
import threading

from locationsharinglib import Person
from locationsharinglib.locationsharinglibexceptions import InvalidData
from requests import RequestException, Session

_LOGGER = logging.getLogger(__name__)

LOCATION_URL = "https://www.google.com/maps/rpc/locationsharing/read"
ROTATE_URL = "https://accounts.google.com/RotateCookies"
LOCATION_PARAMS = {
    "authuser": 2,
    "hl": "en",
    "gl": "us",
    # parametri di rendering della mappa, irrilevanti per la posizione
    "pb": (
        "!1m7!8m6!1m3!1i14!2i8413!3i5385!2i6!3x4095"
        "!2m3!1e0!2sm!3i407105169!3m7!2sen!5e1105!12m4"
        "!1e68!2m2!1sset!2sRoadmap!4e1!5m4!1e4!8m2!1e0!"
        "1e1!6m9!1e12!2i2!26m1!4b1!30m1!"
        "1f1.3953487873077393!39b1!44e1!50e0!23i4111425"
    ),
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"
)
REQUIRED_COOKIES = {"__Secure-1PSID", "__Secure-3PSID"}
TIMEOUT = 30


class GoogleMapsAuthError(Exception):
    """Cookie mancanti o sessione Google non più valida."""


class GoogleMapsApiError(Exception):
    """Errore di rete o risposta inattesa."""


def _is_google_domain(domain: str) -> bool:
    domain = domain.lstrip(".").lower()
    return "google." in domain or domain.endswith("youtube.com")


def parse_cookie_text(text: str) -> list[dict]:
    """Legge un file cookies.txt (formato Netscape), compresi i cookie #HttpOnly_."""
    cookies = []
    for raw in text.splitlines():
        line = raw.strip()
        httponly = False
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_") :]
            httponly = True
        elif not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 7:
            fields = line.split()
        if len(fields) < 6:
            continue
        domain, _flag, path, secure, expires, name = fields[:6]
        value = fields[6] if len(fields) > 6 else ""
        if not _is_google_domain(domain):
            continue
        try:
            expiry = int(float(expires))
        except ValueError:
            expiry = 0
        cookies.append(
            {
                "domain": domain,
                "path": path or "/",
                "secure": secure.upper() == "TRUE",
                "expires": expiry or None,
                "name": name,
                "value": value,
                "httponly": httponly,
            }
        )
    return cookies


class GoogleMapsClient:
    """Sessione autenticata su Google Maps, salvata su file."""

    def __init__(self, cookie_path: str, email: str, cookie_text: str | None = None) -> None:
        """Crea la sessione dal testo dei cookie o dal file."""
        self.cookie_path = cookie_path
        self.email = email
        self._lock = threading.Lock()
        if cookie_text is None:
            with open(cookie_path, encoding="utf-8") as fh:
                cookie_text = fh.read()
        cookies = parse_cookie_text(cookie_text)
        if not REQUIRED_COOKIES & {c["name"] for c in cookies}:
            raise GoogleMapsAuthError(
                "Nei cookie mancano __Secure-1PSID / __Secure-3PSID"
            )
        self.session = Session()
        self.session.headers["User-Agent"] = USER_AGENT
        for c in cookies:
            self.session.cookies.set(
                c["name"],
                c["value"],
                domain=c["domain"],
                path=c["path"],
                secure=c["secure"],
                expires=c["expires"],
                rest={"HttpOnly": None} if c["httponly"] else {},
            )
        self._saved_signature = None

    def fetch(self) -> dict[str, Person]:
        """Legge le persone che condividono la posizione."""
        with self._lock:
            try:
                resp = self.session.get(LOCATION_URL, params=LOCATION_PARAMS, timeout=TIMEOUT)
            except RequestException as err:
                raise GoogleMapsApiError(f"Errore di rete: {err}") from err
        if resp.status_code in (401, 403):
            raise GoogleMapsAuthError(f"Google ha risposto HTTP {resp.status_code}")
        if not resp.ok:
            raise GoogleMapsApiError(f"Google ha risposto HTTP {resp.status_code}")
        try:
            data = json.loads(resp.text.split("'", 1)[1])
        except (ValueError, IndexError, TypeError) as err:
            raise GoogleMapsApiError("Risposta di Google non leggibile") from err
        # come in locationsharinglib: 'GgA=' nel campo 6 = sessione non autenticata
        if len(data) > 6 and data[6] == "GgA=":
            raise GoogleMapsAuthError("La sessione Google non è più valida")

        people: dict[str, Person] = {}
        for info in data[0] or []:
            try:
                person = Person(info)
            except InvalidData:
                continue
            if person.id is not None:
                people[str(person.id)] = person
        me = self._authenticated_person(data)
        if me is not None:
            people[self.email] = me
        return people

    def _authenticated_person(self, data) -> Person | None:
        """Posizione dell'account usato per l'accesso, se Google la fornisce."""
        try:
            return Person(
                [self.email, data[9][1], None, None, None, None,
                 [None, None, self.email, self.email],
                 None, None, None, None, None, None, None]
            )
        except (IndexError, TypeError, InvalidData):
            return None

    def rotate(self) -> bool:
        """Chiede a Google di rinnovare __Secure-1PSIDTS, come fa il browser."""
        with self._lock:
            try:
                resp = self.session.post(
                    ROTATE_URL,
                    headers={"Content-Type": "application/json"},
                    data='[000,"-0000000000000000000"]',
                    timeout=TIMEOUT,
                )
            except RequestException as err:
                _LOGGER.debug("Rinnovo cookie non riuscito: %s", err)
                return False
        if not resp.ok:
            _LOGGER.debug("Rinnovo cookie: HTTP %s", resp.status_code)
        return resp.ok

    def save_if_changed(self) -> bool:
        """Scrive i cookie su file (formato Netscape) se sono cambiati."""
        with self._lock:
            jar = [c for c in self.session.cookies if _is_google_domain(c.domain or "")]
            signature = tuple(sorted((c.domain, c.path, c.name, c.value) for c in jar))
            if signature == self._saved_signature:
                return False
            lines = [
                "# Netscape HTTP Cookie File",
                "# Gestito da google_maps_sharing: non modificare mentre HA è acceso.",
                "",
            ]
            for c in jar:
                prefix = "#HttpOnly_" if c.has_nonstandard_attr("HttpOnly") else ""
                domain = c.domain or ""
                lines.append(
                    "\t".join(
                        [
                            prefix + domain,
                            "TRUE" if domain.startswith(".") else "FALSE",
                            c.path or "/",
                            "TRUE" if c.secure else "FALSE",
                            str(int(c.expires or 0)),
                            c.name,
                            c.value or "",
                        ]
                    )
                )
            tmp = f"{self.cookie_path}.tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(lines) + "\n")
            os.replace(tmp, self.cookie_path)
            self._saved_signature = signature
            return True
