"""Telephony providers for the Voice Notification Agent (Agent 16).

Phase 1 used a simulated provider (log only). Phase 2 adds real
providers that plug into the same `VoiceProvider` interface:

  - TwilioProvider    — Twilio Voice API (international)
  - ExotelProvider    — Exotel (India)
  - MSG91Provider     — MSG91 (India)

A provider is only used if its API credentials are present in the
environment (e.g. TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN). If
credentials are missing, the provider degrades to the simulated
behaviour and says so — it never silently pretends a call was placed.

All providers honour the same gates enforced by Agent 16 (approved
message, consent, calling hours, identity check) and return a call-log
entry with an acknowledgement status.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..agents.agent_16_voice_notification import (
    VoiceProvider, SimulatedVoiceProvider,
)


class _HTTPBase(VoiceProvider):
    """Shared HTTP plumbing for REST telephony providers."""

    def __init__(self, log_path: str, timeout: int = 30):
        self.log_path = log_path
        self.timeout = timeout
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    def _log(self, entry: Dict[str, Any]) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _post(self, url: str, payload: Dict[str, Any],
              headers: Dict[str, str]) -> Dict[str, Any]:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _tts(message: str) -> str:
        """Wrap a message for TTS delivery."""
        return message

    def _simulate(self, recipient: str, message: str,
                  note: str) -> Dict[str, Any]:
        """Shared simulated fallback (used when credentials are missing)."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recipient": recipient,
            "provider": "simulated",
            "result": "simulated",
            "acknowledgement": "simulated_ack",
            "note": note,
        }
        self._log(entry)
        return entry


class TwilioProvider(_HTTPBase):
    """Twilio Voice API. Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    and a TWILIO_FROM_NUMBER env var (a Twilio phone number)."""

    def __init__(self, log_path: str, timeout: int = 30):
        super().__init__(log_path, timeout)
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_FROM_NUMBER", "")

    @property
    def configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)

    def place_call(self, recipient: str, message: str) -> Dict[str, Any]:
        if not self.configured:
            return self._simulate(recipient, message,
                                  note="twilio_not_configured")
        url = ("https://api.twilio.com/2010-04-01/Accounts/"
               f"{self.account_sid}/Calls.json")
        headers = {
            "Authorization": "Basic " +
            base64.b64encode(
                f"{self.account_sid}:{self.auth_token}".encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            # Twilio's Calls API accepts a `Message` parameter directly,
            # which it converts to speech (TTS) — no TwiML endpoint needed.
            # (The previous implementation pointed `Url` at a non-existent
            # `Twiml?message=` endpoint, so the call could never speak.)
            result = self._post(url, {
                "To": recipient,
                "From": self.from_number,
                "Message": self._tts(message),
            }, headers)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recipient": recipient,
                "provider": "twilio",
                "call_sid": result.get("sid"),
                "result": "placed",
                "acknowledgement": "pending_callback",
            }
            self._log(entry)
            return entry
        except Exception as e:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recipient": recipient,
                "provider": "twilio",
                "result": "error",
                "error": str(e)[:200],
                "acknowledgement": "failed",
            }
            self._log(entry)
            return entry


class ExotelProvider(_HTTPBase):
    """Exotel (India). Requires EXOTEL_ACCOUNT_ID and EXOTEL_AUTH_KEY."""

    def __init__(self, log_path: str, timeout: int = 30):
        super().__init__(log_path, timeout)
        self.account_id = os.environ.get("EXOTEL_ACCOUNT_ID", "")
        self.auth_key = os.environ.get("EXOTEL_AUTH_KEY", "")
        self.from_number = os.environ.get("EXOTEL_FROM_NUMBER", "")

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.auth_key and self.from_number)

    def place_call(self, recipient: str, message: str) -> Dict[str, Any]:
        if not self.configured:
            return self._simulate(recipient, message,
                                  note="exotel_not_configured")
        # Production broadcast endpoint (the previous implementation used
        # the `/v1/test/` sandbox path, which is not a production voice API).
        url = "https://api.exotel.com/v1/broadcasts"
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "X-EXOTEL-AUTH-KEY": self.auth_key}
        try:
            result = self._post(url, {
                "account_id": self.account_id,
                "from": self.from_number,
                "to": recipient,
                "message": self._tts(message),
            }, headers)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recipient": recipient,
                "provider": "exotel",
                "broadcast_id": result.get("id"),
                "result": "placed",
                "acknowledgement": "pending_callback",
            }
            self._log(entry)
            return entry
        except Exception as e:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recipient": recipient,
                "provider": "exotel",
                "result": "error",
                "error": str(e)[:200],
                "acknowledgement": "failed",
            }
            self._log(entry)
            return entry


class MSG91Provider(_HTTPBase):
    """MSG91 (India). Requires MSG91_AUTH_KEY and MSG91_SENDER_ID."""

    def __init__(self, log_path: str, timeout: int = 30):
        super().__init__(log_path, timeout)
        self.auth_key = os.environ.get("MSG91_AUTH_KEY", "")
        self.sender_id = os.environ.get("MSG91_SENDER_ID", "")

    @property
    def configured(self) -> bool:
        return bool(self.auth_key)

    def place_call(self, recipient: str, message: str) -> Dict[str, Any]:
        if not self.configured:
            return self._simulate(recipient, message,
                                  note="msg91_not_configured")
        url = "https://control.msg91.com/api/v5/voice"
        headers = {"authkey": self.auth_key,
                   "Content-Type": "application/json"}
        try:
            data = json.dumps({
                "mobiles": recipient,
                "message": self._tts(message),
                "sender": self.sender_id or "LFAGNT",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers,
                                         method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recipient": recipient,
                "provider": "msg91",
                "result": "placed" if result.get("type") == "success" else "error",
                "acknowledgement": "pending_callback",
            }
            self._log(entry)
            return entry
        except Exception as e:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recipient": recipient,
                "provider": "msg91",
                "result": "error",
                "error": str(e)[:200],
                "acknowledgement": "failed",
            }
            self._log(entry)
            return entry


def build_voice_provider(settings, log_path: str) -> VoiceProvider:
    """Pick a voice provider based on config + available credentials.

    Config `agents.voice.provider` selects the intended provider
    (simulated | twilio | exotel | msg91). If the selected provider's
    credentials are missing, it degrades to simulated (and says so in
    the call log), so the platform never falsely reports a real call.
    """
    provider_name = getattr(settings.voice, "provider", "simulated")
    if provider_name == "twilio":
        p = TwilioProvider(log_path)
        return p if p.configured else SimulatedVoiceProvider(log_path)
    if provider_name == "exotel":
        p = ExotelProvider(log_path)
        return p if p.configured else SimulatedVoiceProvider(log_path)
    if provider_name == "msg91":
        p = MSG91Provider(log_path)
        return p if p.configured else SimulatedVoiceProvider(log_path)
    return SimulatedVoiceProvider(log_path)