"""
Flask backend for the Scholarship Outreach Dashboard

This simple API receives a URL pointing to a college “faculty” or “department” page
and attempts to extract useful outreach contacts from the page.  It uses
BeautifulSoup to parse the HTML and regular expressions to identify people’s
names, designations, email addresses and Indian‐style phone numbers.  A very
light heuristic is applied to guess a high‐level department (e.g. Engineering,
Science, Arts) by scanning the surrounding text for common keywords.  The
resulting contacts are returned as a JSON array.

The API exposes a single endpoint:

    POST /api/extract

Body JSON should contain a single key, ``url``, with the page to
scrape.  The server responds with a list of objects, each containing
``name``, ``designation``, ``department``, ``email`` and ``phone`` keys.  If an
error occurs while fetching or parsing the page, an error message will be
returned instead.

To run this server locally:

    pip install -r requirements.txt
    python app.py

By default the server listens on port 5000 and accepts requests from any
origin (CORS is enabled).  Adjust as needed for production deployment.
"""

from __future__ import annotations

import re
from typing import List, Dict, Optional, Union
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
try:
    # We attempt to import Flask.  In many offline environments Flask
    # isn’t available, so these imports may fail.  If Flask is present the
    # below server will be defined and used when running ``python app.py``.
    from flask import Flask, jsonify, request
    from flask_cors import CORS  # type: ignore

    _HAS_FLASK = True
except Exception:
    _HAS_FLASK = False

if _HAS_FLASK:
    app = Flask(__name__)
    CORS(app)  # allow cross‑origin requests for front‑end development


def _normalise_url(url: str) -> str:
    """Return a fully qualified URL, prepending a scheme if missing.

    Many university websites use protocol‑relative URLs (``//example.com/page``)
    or omit the scheme entirely (``example.com/page``).  Requests will raise
    ``MissingSchema`` if no scheme is supplied, so this helper ensures that
    ``https://`` is always prefixed.  If the URL already contains a scheme,
    it is returned unchanged.
    """
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    parsed = urlparse(url)
    if not parsed.scheme:
        return "https://" + url
    return url


def _extract_emails(text: str) -> List[str]:
    """Return a list of unique email addresses found in the given text."""
    email_regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    return list({m.group().strip() for m in email_regex.finditer(text)})


def _extract_phones(text: str) -> List[str]:
    """Return a list of unique Indian phone numbers found in the given text.

    The regex looks for patterns like ``+91xxxxxxxxxx`` or ``0xxxxxxx`` with
    optional separators.  It is intentionally generous; numbers may include
    spaces or hyphens.  Prefixes starting with +91 or a leading zero with
    three–four digit area codes are captured.
    """
    phone_regex = re.compile(
        r"(?:\+91[\s-]?)?[6-9]\d{9}|0\d{2,4}[\s-]?\d{6,8}", re.MULTILINE
    )
    return list({re.sub(r"\s+", "", m.group().strip()) for m in phone_regex.finditer(text)})


def _guess_department(context: str) -> Optional[str]:
    """Given a snippet of text, attempt to guess a broad department name.

    This helper scans the context for keywords such as ``Engineering``, ``Science``,
    ``Arts``, ``Commerce``, ``Management`` etc.  The first matching keyword
    (case‑insensitive) is returned.  If nothing matches, ``None`` is returned.
    """
    department_keywords = [
        "Engineering",
        "Science",
        "Arts",
        "Commerce",
        "Management",
        "Technology",
        "Business",
        "Medical",
    ]
    for dept in department_keywords:
        if re.search(r"\b" + re.escape(dept) + r"\b", context, re.IGNORECASE):
            return dept
    return None


def extract_contacts(url: str) -> Union[List[Dict[str, Optional[str]]], Dict[str, str]]:
    """Scrape a web page and return a list of contact dictionaries.

    Each contact dictionary contains ``name``, ``designation``, ``department``,
    ``email`` and ``phone`` keys.  Some values may be ``None`` if they could
    not be determined.  If an error occurs when fetching or parsing the page,
    a dict with an ``error`` key is returned instead.
    """
    try:
        full_url = _normalise_url(url)
        response = requests.get(full_url, timeout=15)
        response.raise_for_status()
    except Exception as exc:
        return {"error": f"Failed to fetch URL: {exc}"}

    # Parse HTML content
    soup = BeautifulSoup(response.text, "html.parser")
    # Extract visible text; use newlines to preserve some structure
    text = soup.get_text(separator="\n")
    # Normalise whitespace
    text = re.sub(r"\xa0", " ", text)
    text = re.sub(r"\s+", " ", text)

    # Precompute all emails and phones on the page
    global_emails = _extract_emails(text)
    global_phones = _extract_phones(text)

    contacts: List[Dict[str, Optional[str]]] = []

    # Patterns for faculty designations
    designation_keywords = [
        "Professor",
        "Associate Professor",
        "Assistant Professor",
        "HOD",
        "Head",
        "Dean",
        "Director",
        "Coordinator",
        "Principal",
        "Chairperson",
        "Registrar",
    ]
    # Build regex capturing names followed by a designation
    # We allow one to four capitalised words (Dr., initials etc.) before the designation
    name_designation_regex = re.compile(
        r"((?:Dr\.?\s*)?(?:[A-Z][a-zA-Z\'\.-]*\s+){1,4})\s*(" + "|".join(designation_keywords) + r")",
        re.IGNORECASE,
    )

    # Search the entire text for name/designation pairs
    for match in name_designation_regex.finditer(text):
        raw_name = match.group(1).strip()
        designation = match.group(2).title()
        name = re.sub(r"\s+", " ", raw_name)

        start_idx = match.start()
        end_idx = match.end()

        # Look around the match for department hints
        context_before = text[max(0, start_idx - 300) : start_idx]
        context_after = text[end_idx : end_idx + 300]
        department = _guess_department(context_before) or _guess_department(context_after)

        # Find an email and phone close to this match
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", context_after)
        phone_match = re.search(
            r"(?:\+91[\s-]?)?[6-9]\d{9}|0\d{2,4}[\s-]?\d{6,8}", context_after
        )
        email = email_match.group().strip() if email_match else None
        phone = (
            re.sub(r"\s+", "", phone_match.group().strip()) if phone_match else None
        )

        contacts.append(
            {
                "name": name,
                "designation": designation,
                "department": department,
                "email": email,
                "phone": phone,
            }
        )

    # Student lead patterns (placement cell, student council, cultural head)
    student_keywords = ["Placement Cell", "Student Council", "Cultural Head"]
    for keyword in student_keywords:
        # Pattern: name followed by keyword (e.g. “John Doe – Placement Cell”)
        pattern = re.compile(
            r"((?:[A-Z][a-zA-Z\'\.-]*\s+){1,4}[A-Z][a-zA-Z\'\.-]*)\s*[-,;:]?\s*"
            + re.escape(keyword),
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            raw_name = match.group(1).strip()
            name = re.sub(r"\s+", " ", raw_name)
            designation = keyword
            start_idx = match.start()
            end_idx = match.end()
            context_before = text[max(0, start_idx - 300) : start_idx]
            context_after = text[end_idx : end_idx + 300]
            department = _guess_department(context_before) or _guess_department(context_after)
            email_match = re.search(
                r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", context_after
            )
            phone_match = re.search(
                r"(?:\+91[\s-]?)?[6-9]\d{9}|0\d{2,4}[\s-]?\d{6,8}", context_after
            )
            email = email_match.group().strip() if email_match else None
            phone = (
                re.sub(r"\s+", "", phone_match.group().strip()) if phone_match else None
            )
            contacts.append(
                {
                    "name": name,
                    "designation": designation,
                    "department": department,
                    "email": email,
                    "phone": phone,
                }
            )

    # De‑duplicate contacts by (name, designation, email)
    seen = set()
    unique_contacts: List[Dict[str, Optional[str]]] = []
    for c in contacts:
        key = (c["name"], c["designation"], c.get("email"))
        if key not in seen:
            seen.add(key)
            unique_contacts.append(c)

    return unique_contacts


@app.route("/api/extract", methods=["POST"])
def api_extract() -> tuple:
    """HTTP handler for contact extraction.

    Accepts JSON with a ``url`` property, passes it to ``extract_contacts`` and
    returns a JSON array of contact dictionaries.  Errors will return a
    400/500 status with an appropriate JSON body.
    """
    data = request.get_json(silent=True)
    if not data or not data.get("url"):
        return jsonify({"error": "A JSON payload with a 'url' field is required."}), 400
    url = data["url"]
    result = extract_contacts(url)
    if isinstance(result, dict) and result.get("error"):
        return jsonify(result), 500
    return jsonify(result), 200


if __name__ == "__main__":  # pragma: no cover
    if _HAS_FLASK:
        # If Flask is available, use it – developers may prefer this when
        # running locally with a full Python environment.  Flask handles
        # routing and JSON encoding automatically.
        app.run(host="0.0.0.0", port=5000, debug=True)
    else:
        # Fallback: use the built‑in HTTP server from the standard library.
        import json
        import sys
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from urllib.parse import urlparse

        class Handler(BaseHTTPRequestHandler):
            """Minimal HTTP handler supporting CORS and a single POST endpoint."""

            def _set_headers(self, status_code: int = 200):
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                # Allow all origins – adjust in production
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header(
                    "Access-Control-Allow-Headers", "Content-Type, Authorization"
                )
                self.send_header(
                    "Access-Control-Allow-Methods", "POST, GET, OPTIONS"
                )
                self.end_headers()

            def do_OPTIONS(self):  # Handle CORS preflight requests
                self._set_headers()
                self.wfile.write(b"{}")

            def do_POST(self):
                parsed = urlparse(self.path)
                if parsed.path != "/api/extract":
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"error": "Not found"}).encode())
                    return
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length else b""
                try:
                    data = json.loads(body.decode() or '{}')
                except Exception:
                    self._set_headers(400)
                    self.wfile.write(
                        json.dumps({"error": "Invalid JSON payload"}).encode()
                    )
                    return
                url = data.get("url") if isinstance(data, dict) else None
                if not url:
                    self._set_headers(400)
                    self.wfile.write(
                        json.dumps(
                            {
                                "error": "A JSON payload with a 'url' field is required."
                            }
                        ).encode()
                    )
                    return
                result = extract_contacts(url)
                if isinstance(result, dict) and result.get("error"):
                    self._set_headers(500)
                    self.wfile.write(json.dumps(result).encode())
                else:
                    self._set_headers(200)
                    self.wfile.write(json.dumps(result).encode())

        server = HTTPServer(("0.0.0.0", 5000), Handler)
        print("* Running on http://0.0.0.0:5000 (fallback builtin server)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n* Shutting down server…")
            server.server_close()