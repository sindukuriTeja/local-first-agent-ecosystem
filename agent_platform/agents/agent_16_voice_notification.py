"""Agent 16 — Voice Notification Agent.

From the architecture:
  Approved message only • consent • calling hours
  identity check • acknowledgement

Sends voice notifications (calls / voice messages) to approved
recipients. Hard gates, all enforced before any "call":
  1. Approved message only — the message must have passed an approval
     (from Reporting #15 or Compliance #8).
  2. Consent — the recipient must have given consent on file.
  3. Calling hours — only within the configured window (default
     09:00–18:00 Asia/Calcutta).
  4. Identity check — the caller identity is verified before the call.
  5. Acknowledgement — the call log records heard / missed /
     acknowledged / wrong person, fed back to Compliance & Risk (#8).

Phase 1 uses a simulated telephony provider: the call is logged, not
dialed. A real provider plugs into `VoiceProvider`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

from ..core.base_agent import AgentContext, AgentResult, BaseAgent

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


class VoiceProvider:
    """Interface for a telephony provider."""

    def place_call(self, recipient: str, message: str) -> Dict[str, Any]:
        raise NotImplementedError


class SimulatedVoiceProvider(VoiceProvider):
    """Phase 1 provider: logs the call, never dials."""

    def __init__(self, log_path: str):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    def place_call(self, recipient: str, message: str) -> Dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recipient": recipient,
            "message": message,
            "provider": "simulated",
            "result": "simulated",
            "acknowledgement": "simulated_ack",
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry


class VoiceNotificationAgent(BaseAgent):
    agent_id = "agent_16_voice_notification"
    name = "Voice Notification Agent"
    responsibility = (
        "Send approved voice messages to consented recipients within "
        "calling hours, with identity check and acknowledgement. Log the "
        "call result back to Compliance & Risk."
    )

    def __init__(self, services, provider: Optional[VoiceProvider] = None):
        super().__init__(services)
        if provider is None:
            # Config-driven provider (simulated | twilio | exotel | msg91).
            # Degrades to simulated when the chosen provider's credentials
            # are absent, so the platform never falsely reports a real call.
            from ..core.telephony import build_voice_provider
            log_path = services.settings.resolve_path(
                os.path.join(services.settings.storage.data_dir, "voice_call_log.jsonl")
            )
            provider = build_voice_provider(services.settings, log_path)
        self.provider = provider

    # ---------- gates ----------

    def _in_calling_hours(self) -> bool:
        hours = self.settings.voice.calling_hours
        tz_name = hours.get("timezone", "Asia/Calcutta")
        try:
            if ZoneInfo is not None:
                now = datetime.now(ZoneInfo(tz_name))
            else:  # pragma: no cover
                now = datetime.now()
        except Exception:
            now = datetime.now()
        start = time.fromisoformat(hours.get("start", "09:00"))
        end = time.fromisoformat(hours.get("end", "18:00"))
        return start <= now.time() <= end

    def _has_consent(self, recipient: str, ctx: AgentContext) -> bool:
        """Consent must be on file in the knowledge store as a fact."""
        facts = self.knowledge.facts_for(subject=recipient,
                                         tenant=ctx.identity.tenant)
        return any(f.get("predicate") == "voice_consent"
                   and f.get("confidence", 0) > 0 for f in facts)

    # ---------- run ----------

    def run(self, ctx: AgentContext) -> AgentResult:
        # 1. Approved message only
        message = ctx.state.get("voice_message")
        alerts = ctx.state.get("voice_alerts", []) or []
        if not message and not alerts:
            self._audit(ctx, "no_approved_message", result="blocked")
            return AgentResult(
                self.agent_id, "error",
                error="No approved message or alerts in state. Voice "
                      "notifications require an approved message (from "
                      "Reporting #15) or alerts (from Compliance #8).",
            )

        text = self._compose_message(message, alerts)

        # 2. Recipients (approved list in state or config)
        recipients: List[str] = ctx.state.get("voice_recipients", []) or []
        if not recipients:
            self._audit(ctx, "no_recipients", result="blocked")
            return AgentResult(
                self.agent_id, "error",
                error="No approved recipients provided (state['voice_recipients']).",
            )

        # 3. Caller role check
        if not self.policy.can_voice(ctx.identity):
            self._audit(ctx, "voice_role_denied",
                        detail={"role": ctx.identity.role}, result="denied")
            return AgentResult(
                self.agent_id, "error",
                error=f"Role '{ctx.identity.role}' is not authorized for "
                      f"voice notifications.",
            )

        # 4. Calling hours
        if not self._in_calling_hours():
            self._audit(ctx, "outside_calling_hours", result="blocked")
            return AgentResult(
                self.agent_id, "error",
                answer="Blocked: outside configured calling hours.",
                data={"blocked_reason": "calling_hours"},
            )

        # 5. Per-recipient: consent + identity check, then call
        call_log: List[Dict[str, Any]] = []
        for recipient in recipients:
            if not self._has_consent(recipient, ctx):
                call_log.append({"recipient": recipient, "result": "no_consent",
                                 "skipped": True})
                self._audit(ctx, "consent_missing",
                            detail={"recipient": recipient}, result="skipped")
                continue
            # Identity check (simulated in Phase 1: recipient record must
            # exist in the knowledge store)
            if self.settings.voice.identity_check_required:
                facts = self.knowledge.facts_for(subject=recipient,
                                                 tenant=ctx.identity.tenant)
                if not facts:
                    call_log.append({"recipient": recipient,
                                     "result": "identity_check_failed",
                                     "skipped": True})
                    self._audit(ctx, "identity_check_failed",
                                detail={"recipient": recipient}, result="skipped")
                    continue

            result = self.provider.place_call(recipient, text)
            call_log.append({"recipient": recipient, "result": result.get("result"),
                             "acknowledgement": result.get("acknowledgement"),
                             "skipped": False})
            self._audit(ctx, "voice_call",
                        detail={"recipient": recipient,
                                "provider": self.settings.voice.provider,
                                "result": result.get("result")},
                        result=result.get("result"))

        # 6. Feed call log back to Compliance & Risk (#8)
        ctx.state["voice_call_log"] = call_log
        ctx.state["route_to_compliance"] = True

        placed = [c for c in call_log if not c.get("skipped")]
        skipped = [c for c in call_log if c.get("skipped")]

        return AgentResult(
            self.agent_id, "ok",
            answer=(
                f"Voice notification run complete: {len(placed)} call(s) "
                f"placed (provider: {self.settings.voice.provider}), "
                f"{len(skipped)} skipped. Call log recorded and fed back to "
                f"Compliance & Risk."
            ),
            data={
                "message": text,
                "call_log": call_log,
                "placed": len(placed),
                "skipped": len(skipped),
                "provider": self.settings.voice.provider,
                "route_to_compliance": True,
            },
            sources=ctx.sources,
        )

    @staticmethod
    def _compose_message(message: Optional[Dict[str, Any]],
                         alerts: List[Dict[str, Any]]) -> str:
        parts = []
        if message:
            parts.append(f"Report update: {message.get('report_title', '')}.")
            for m in message.get("key_metrics", []) or []:
                parts.append(f"{m.get('metric', '')}: {m.get('value', '')}.")
        for a in alerts:
            parts.append(f"Alert: {a.get('message', '')} "
                         f"(severity: {a.get('severity', 'n/a')}).")
        parts.append("This is an automated notification from the internal platform.")
        return " ".join(parts)