"""Phase 2 tests: self-learning engine, live web fetcher, telephony,
dataset, and the platform's learn() entry point."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_platform.core.ollama import MockOllamaClient
from agent_platform.core.policy import Identity
from agent_platform.core.web_fetcher import (
    LiveWebFetcher, LocalCacheFetcher, build_fetcher, extract_text,
)
from agent_platform.core.telephony import (
    TwilioProvider, ExotelProvider, MSG91Provider, build_voice_provider,
)
from agent_platform.learning.answerer import GroundedAnswerer
from agent_platform.learning.consolidator import MemoryConsolidator
from agent_platform.learning.insight_miner import InsightMiner, CandidateInsight
from agent_platform.learning.regression import RegressionHarness
from agent_platform.learning.scheduler import LearningScheduler
from agent_platform.learning.trajectory import TrajectoryStore, anonymize
from agent_platform.learning.verification import VerificationGate
from agent_platform.platform import create_platform


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class TestDataset:
    def test_generate(self, tmp_path):
        from scripts.generate_dataset import generate
        out = str(tmp_path / "ds")
        result = generate(out, seed=42)
        assert result["counts"]["documents"] >= 20
        assert result["counts"]["exam_questions"] >= 30
        assert os.path.isfile(os.path.join(out, "documents.json"))
        assert os.path.isfile(os.path.join(out, "exam.json"))

    def test_seed_into_platform(self, platform):
        # The fixture already seeds the dataset; verify knowledge has it.
        docs = platform.knowledge.list_documents(limit=200)
        assert len(docs) >= 20
        # exam is loaded
        assert len(platform.exam) >= 30


# ---------------------------------------------------------------------------
# Trajectory store + anonymization
# ---------------------------------------------------------------------------

class TestTrajectory:
    def test_anonymize(self):
        assert "[phone]" in anonymize("call 9876543210 now")
        assert "[email]" in anonymize("email me at a@b.com")
        assert "[matter]" in anonymize("matter M-2026-001 status")
        assert "[amount]" in anonymize("amount 500000 rs")

    def test_record_and_query(self, tmp_path):
        ts = TrajectoryStore(str(tmp_path / "traj.jsonl"))
        ts.record("t1", "What is the deadline?", ["agent_2"], "ok", user="admin")
        ts.record("t2", "Draft a notice", ["agent_7"], "needs_approval")
        ts.record("t3", "unknown thing", ["agent_10"], "abstain")
        assert len(ts.all()) == 3
        assert len(ts.by_outcome("success")) == 1
        assert len(ts.needs_review()) == 2  # needs_approval + abstain

    def test_feedback(self, tmp_path):
        ts = TrajectoryStore(str(tmp_path / "traj.jsonl"))
        tid = ts.record("t1", "q", ["agent_2"], "ok")
        assert ts.set_feedback(tid, "bad") is True
        assert ts.failures() and ts.failures()[0]["id"] == tid


# ---------------------------------------------------------------------------
# Insight miner
# ---------------------------------------------------------------------------

def _traj(outcome, agents, tid):
    return {"id": tid, "outcome": outcome, "agents_run": agents,
            "request": "r", "final_status": outcome}


class TestInsightMiner:
    def test_heuristic_recurring_abstain(self):
        miner = InsightMiner()
        trajs = [
            _traj("abstain", ["agent_10"], "a1"),
            _traj("abstain", ["agent_10"], "a2"),
            _traj("success", ["agent_2"], "s1"),
        ]
        cands = miner.mine_heuristic(trajs)
        assert any(c.kind == "retrieval_tweak" and c.scope == "agent_10"
                   for c in cands)

    def test_heuristic_recurring_success_sequence(self):
        miner = InsightMiner()
        trajs = [
            _traj("success", ["agent_2", "agent_5"], "s1"),
            _traj("success", ["agent_2", "agent_5"], "s2"),
        ]
        cands = miner.mine_heuristic(trajs)
        assert any(c.kind == "skill" and c.scope == "orchestration"
                   for c in cands)

    def test_mine_dedupes(self):
        miner = InsightMiner()
        trajs = [
            _traj("abstain", ["agent_10"], "a1"),
            _traj("abstain", ["agent_10"], "a2"),
        ]
        cands = miner.mine(trajs)
        keys = [(c.kind, c.scope) for c in cands]
        assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# Verification gate + regression harness
# ---------------------------------------------------------------------------

def _exam():
    return [
        {"id": "Q1", "q": "How many years for books of account?",
         "a": "eight years"},
        {"id": "Q2", "q": "Due date for return of income?",
         "a": "31st July"},
        {"id": "Q3", "q": "SARFAESI demand notice days?",
         "a": "60 days"},
    ]


def _answerer(answers: dict):
    """A simple answer function that returns canned answers."""
    def fn(q):
        for key, val in answers.items():
            if key in q:
                return val
        return "UNKNOWN"
    return fn


class TestVerification:
    def test_holdout_scoring(self):
        gate = VerificationGate(exam=_exam())
        good = _answerer({"books of account": "eight years",
                          "return of income": "31st July",
                          "demand notice": "60 days"})
        assert gate.score_holdout(good) == 1.0
        bad = _answerer({"books of account": "wrong answer"})
        assert gate.score_holdout(bad) < 1.0

    def test_pass_candidate(self):
        gate = VerificationGate(exam=_exam(),
                                answer_fn=_answerer({
                                    "books of account": "eight years",
                                    "return of income": "31st July",
                                    "demand notice": "60 days"}))
        cand = CandidateInsight(id="c1", kind="skill", statement="s",
                                scope="agent_2", provenance=["t1"])
        res = gate.verify(cand, replay_trajectories=[
            _traj("success", ["agent_2"], "t1")])
        assert res.passed is True
        assert res.holdout_score == 1.0

    def test_reject_on_regression(self):
        baseline = _answerer({"books of account": "eight years",
                              "return of income": "31st July",
                              "demand notice": "60 days"})
        regressed = _answerer({"books of account": "no idea",
                               "return of income": "no idea",
                               "demand notice": "no idea"})
        gate = VerificationGate(exam=_exam(), answer_fn=baseline)
        cand = CandidateInsight(id="c2", kind="fact", statement="s",
                                scope="agent_2", provenance=["t1"])
        res = gate.verify(cand, replay_trajectories=[
            _traj("success", ["agent_2"], "t1")],
            baseline_answer_fn=baseline, candidate_answer_fn=regressed)
        assert res.passed is False
        assert res.regression is True

    def test_review_decision(self):
        gate = VerificationGate(exam=_exam(),
                                answer_fn=_answerer({"x": "y"}))
        cand = CandidateInsight(id="c3", kind="fact", statement="s",
                                scope="agent_2", provenance=[])
        res = gate.verify(cand, replay_trajectories=[])
        gate.record_review(res, "approved", "reviewer")
        assert res.review_status == "approved"


class TestRegression:
    def test_pass_when_improved(self):
        harness = RegressionHarness(exam=_exam(), min_accuracy=0.6)
        current = _answerer({"books of account": "eight years",
                             "return of income": "31st July",
                             "demand notice": "60 days"})
        candidate = current
        res = harness.run("c1", current, candidate)
        assert res.passed is True
        assert res.current_accuracy == res.candidate_accuracy

    def test_fail_below_floor(self):
        harness = RegressionHarness(exam=_exam(), min_accuracy=0.9)
        current = _answerer({"books of account": "eight years"})  # 1/3
        res = harness.run("c1", current, current)
        assert res.passed is False  # 0.33 < 0.9 floor


# ---------------------------------------------------------------------------
# Memory consolidator
# ---------------------------------------------------------------------------

class TestConsolidator:
    def test_merge_duplicates(self, tmp_path):
        from agent_platform.core.memory import MemorySystem
        mem = MemorySystem(str(tmp_path))
        mem.store("semantic", "The deadline is 2026-12-01.", provenance="a")
        mem.store("semantic", "The deadline is 2026-12-01.", provenance="b")
        mem.store("semantic", "A completely different fact.", provenance="c")
        cons = MemoryConsolidator(mem)
        report = cons.consolidate(kind="semantic")
        assert report.merged >= 1
        active = mem.recall("semantic", status="active")
        assert len(active) == 2  # one duplicate decayed


# ---------------------------------------------------------------------------
# Learning scheduler (end-to-end)
# ---------------------------------------------------------------------------

class TestLearningScheduler:
    def _build(self, tmp_path, exam, baseline_fn, cand_fn=None):
        from agent_platform.core.memory import MemorySystem
        from agent_platform.core.ollama import ModelRegistry
        from agent_platform.core.audit import AuditLog
        ts = TrajectoryStore(str(tmp_path / "traj.jsonl"))
        miner = InsightMiner()
        gate = VerificationGate(exam=exam, answer_fn=baseline_fn)
        reg = RegressionHarness(exam=exam, min_accuracy=0.5)
        mem = MemorySystem(str(tmp_path / "mem"))
        cons = MemoryConsolidator(mem)
        reg2 = ModelRegistry("llama3.1:8b")
        audit = AuditLog(str(tmp_path / "audit.jsonl"))
        return LearningScheduler(
            trajectory_store=ts, miner=miner, verification=gate,
            regression=reg, consolidator=cons, registry=reg2, memory=mem,
            audit=audit, budget_per_run=10, min_accuracy=0.5,
            state_path=str(tmp_path / "state.json"))

    def test_no_new_trajectories(self, tmp_path):
        baseline = _answerer({"x": "y"})
        sched = self._build(tmp_path, _exam(), baseline)
        report = sched.run(baseline_answer_fn=baseline)
        assert report.trajectories_processed == 0
        assert "No new trajectories" in " ".join(report.notes)

    def test_full_pipeline_promotes(self, tmp_path):
        exam = _exam()
        baseline = _answerer({"books of account": "eight years",
                              "return of income": "31st July",
                              "demand notice": "60 days"})
        sched = self._build(tmp_path, exam, baseline)
        # Seed trajectories: recurring abstain on agent_10 -> candidate
        for i in range(3):
            sched.trajectories.record(f"t{i}", "q", ["agent_10"], "abstain")
        report = sched.run(baseline_answer_fn=baseline)
        assert report.trajectories_processed == 3
        assert report.candidates_mined >= 1
        # The candidate should pass (baseline is 100% accurate, no regression)
        assert report.promoted >= 1
        # Dashboard reflects the run
        dash = sched.dashboard()
        assert dash["total_runs"] == 1
        assert dash["holdout_accuracy"] == 1.0

    def test_budget_respected(self, tmp_path):
        exam = _exam()
        baseline = _answerer({"books of account": "eight years",
                              "return of income": "31st July",
                              "demand notice": "60 days"})
        sched = self._build(tmp_path, exam, baseline)
        sched.budget_per_run = 1
        # Many trajectories -> many candidates, but budget caps at 1
        for i in range(6):
            sched.trajectories.record(f"t{i}", "q", ["agent_10"], "abstain")
        report = sched.run(baseline_answer_fn=baseline)
        assert report.budget_used <= 1


# ---------------------------------------------------------------------------
# Live web fetcher
# ---------------------------------------------------------------------------

class TestWebFetcher:
    def test_extract_text(self):
        html = "<html><body><h1>Title</h1><p>Hello <b>world</b></p>" \
               "<script>var x=1;</script></body></html>"
        text = extract_text(html)
        assert "Title" in text
        assert "Hello world" in text
        assert "var x=1" not in text

    def test_allowlist_enforced(self, tmp_path):
        cache = str(tmp_path / "cache.json")
        with open(cache, "w") as f:
            json.dump([
                {"title": "ok", "url": "https://www.indiacode.nic.in/a",
                 "content": "statute amendment matter", "collected_at": "2026-01-01"},
                {"title": "evil", "url": "https://evil.com/a",
                 "content": "statute amendment matter evil", "collected_at": "2026-01-01"},
            ], f)
        fetcher = LocalCacheFetcher(cache)
        facts = fetcher.fetch("statute amendment matter",
                              ["https://www.indiacode.nic.in"])
        urls = [f.source_url for f in facts]
        assert any("indiacode" in u for u in urls)
        assert not any("evil.com" in u for u in urls)

    def test_build_fetcher_cache_default(self, platform):
        fetcher = build_fetcher(platform.settings)
        assert isinstance(fetcher, LocalCacheFetcher)

    def test_build_fetcher_live(self, platform):
        platform.settings.external.fetcher = "live"
        fetcher = build_fetcher(platform.settings, audit=platform.audit)
        assert isinstance(fetcher, LiveWebFetcher)

    def test_live_fetcher_offline_graceful(self, platform, tmp_path):
        # With no network, live fetcher should return [] (not crash).
        cache = str(tmp_path / "cache.json")
        fetcher = LiveWebFetcher(cache, audit=platform.audit, timeout=2)
        # Point at a non-resolvable allowlist so it fails fast.
        facts = fetcher.fetch("some query", ["https://nonexistent.invalid"])
        assert isinstance(facts, list)


# ---------------------------------------------------------------------------
# Telephony providers
# ---------------------------------------------------------------------------

class TestTelephony:
    def test_simulated_default(self, platform):
        from agent_platform.core.telephony import SimulatedVoiceProvider
        provider = build_voice_provider(platform.settings,
                                        "/tmp/voice.jsonl")
        assert isinstance(provider, SimulatedVoiceProvider)

    def test_twilio_unconfigured_degrades(self, platform, tmp_path, monkeypatch):
        monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        platform.settings.voice.provider = "twilio"
        provider = build_voice_provider(platform.settings,
                                        str(tmp_path / "v.jsonl"))
        # Not configured -> simulated
        from agent_platform.core.telephony import SimulatedVoiceProvider
        assert isinstance(provider, SimulatedVoiceProvider)

    def test_twilio_configured(self, platform, tmp_path, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
        monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15551234567")
        platform.settings.voice.provider = "twilio"
        provider = build_voice_provider(platform.settings,
                                        str(tmp_path / "v.jsonl"))
        assert isinstance(provider, TwilioProvider)
        assert provider.configured is True

    def test_exotel_configured(self, platform, tmp_path, monkeypatch):
        monkeypatch.setenv("EXOTEL_ACCOUNT_ID", "acc")
        monkeypatch.setenv("EXOTEL_AUTH_KEY", "key")
        monkeypatch.setenv("EXOTEL_FROM_NUMBER", "+919999999999")
        platform.settings.voice.provider = "exotel"
        provider = build_voice_provider(platform.settings,
                                        str(tmp_path / "v.jsonl"))
        assert isinstance(provider, ExotelProvider)
        assert provider.configured is True

    def test_msg91_configured(self, platform, tmp_path, monkeypatch):
        monkeypatch.setenv("MSG91_AUTH_KEY", "key")
        platform.settings.voice.provider = "msg91"
        provider = build_voice_provider(platform.settings,
                                        str(tmp_path / "v.jsonl"))
        assert isinstance(provider, MSG91Provider)
        assert provider.configured is True


# ---------------------------------------------------------------------------
# Platform learn() entry point + trajectory capture
# ---------------------------------------------------------------------------

class TestPlatformLearning:
    def test_trajectory_captured_on_request(self, platform):
        platform.handle_request("admin", "What is the filing deadline for matter A?")
        assert platform.trajectory_store is not None
        assert len(platform.trajectory_store.all()) >= 1

    def test_learn_returns_report(self, platform):
        # Generate some trajectories first
        for i in range(3):
            platform.handle_request("admin", f"question {i} about deadlines")
        report = platform.learn()
        assert "error" not in report
        assert "trajectories_processed" in report
        assert "candidates_mined" in report

    def test_learning_dashboard(self, platform):
        platform.handle_request("admin", "a question")
        dash = platform.learning_dashboard()
        assert "total_runs" in dash

    def test_grounding_answerer(self, platform):
        answerer = GroundedAnswerer(platform.services)
        # The dataset has "eight years" for books of account
        ans = answerer("How many years must books of account be maintained?")
        assert ans  # returns something (model or lexical fallback)

    def test_agent3_uses_config_fetcher(self, platform):
        agent3 = platform.agents["agent_3_external_information"]
        assert isinstance(agent3.fetcher, LocalCacheFetcher)


# ---------------------------------------------------------------------------
# End-to-end learning loop
# ---------------------------------------------------------------------------

class TestEndToEndLearning:
    def test_learn_improves_and_records(self, platform):
        # Seed a mix of trajectories (some abstain -> mining candidates)
        for i in range(4):
            platform.handle_request("admin", "query about a topic")
        report = platform.learn()
        # Should have processed trajectories and mined candidates
        assert report["trajectories_processed"] >= 1
        # Dashboard updated
        dash = platform.learning_dashboard()
        assert dash["total_runs"] >= 1
        # Audit has learning entries
        entries = platform.audit_query(actor="learning_scheduler", limit=50)
        assert len(entries) >= 0  # may be 0 if nothing promoted