"""Real-time collaboration workflow engine tests.

Covers: event bus, lifecycle (create -> approve -> start -> work -> input
request/answer -> complete), role gating, visibility, persistence, and the
AI runner integration.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_platform.workflow import (
    APPROVER_PORTALS,
    REQUESTER_PORTALS,
    ST_ASSIGNED,
    ST_COMPLETED,
    ST_IN_PROGRESS,
    ST_PENDING_APPROVAL,
    ST_REJECTED,
    ST_WAITING_INPUT,
    RealtimeBus,
    WorkflowEngine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return RealtimeBus()


@pytest.fixture
def events(bus):
    seen = []
    bus.subscribe(seen.append)
    return seen


@pytest.fixture
def engine(tmp_path, bus, events):
    ai_calls = []

    def ai_runner(user, prompt, state):
        ai_calls.append((user, prompt, state))
        return {
            "status": "ok",
            "answer": f"AI answer to: {prompt}",
            "agent_id": "agent_2_internal_information",
            "sources": ["seed-doc.txt"],
        }

    eng = WorkflowEngine(
        store_path=str(tmp_path / "workflows.jsonl"),
        bus=bus,
        ai_runner=ai_runner,
    )
    eng._test_ai_calls = ai_calls
    return eng


def _create(engine, subject="Lease renewal query"):
    return engine.create_workflow(
        user="client1", portal="client", subject=subject,
        message="Please advise on our lease renewal options.",
    )


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------

class TestRealtimeBus:
    def test_subscribe_publish_unsubscribe(self):
        bus = RealtimeBus()
        seen = []
        sid = bus.subscribe(seen.append)
        assert bus.subscriber_count == 1
        bus.publish({"type": "x"})
        assert seen == [{"type": "x"}]
        bus.unsubscribe(sid)
        assert bus.subscriber_count == 0
        bus.publish({"type": "y"})
        assert seen == [{"type": "x"}]

    def test_bad_subscriber_does_not_break_others(self):
        bus = RealtimeBus()
        seen = []
        bus.subscribe(lambda e: 1 / 0)
        bus.subscribe(seen.append)
        bus.publish({"type": "x"})
        assert seen == [{"type": "x"}]

    def test_multiple_subscribers(self):
        bus = RealtimeBus()
        a, b = [], []
        bus.subscribe(a.append)
        bus.subscribe(b.append)
        bus.publish({"type": "x"})
        assert a == b == [{"type": "x"}]


# ---------------------------------------------------------------------------
# Creation + role gating
# ---------------------------------------------------------------------------

class TestCreation:
    def test_create_from_client(self, engine, events):
        wf = _create(engine)
        assert wf["status"] == ST_PENDING_APPROVAL
        assert wf["created_by"] == "client1"
        assert wf["created_by_portal"] == "client"
        assert wf["assigned_to"] is None
        assert wf["final_response"] is None
        assert events[-1]["type"] == "workflow.created"
        assert events[-1]["workflow_id"] == wf["id"]
        assert events[-1]["status"] == ST_PENDING_APPROVAL

    def test_create_from_tenant(self, engine):
        wf = engine.create_workflow("tenant1", "tenant", "Parking issue", "msg")
        assert wf["status"] == ST_PENDING_APPROVAL
        assert wf["created_by_portal"] == "tenant"

    @pytest.mark.parametrize("portal", ["management", "employee", "counsel", "auditor", "admin"])
    def test_create_rejected_for_non_requester(self, engine, portal):
        with pytest.raises(PermissionError):
            engine.create_workflow("u1", portal, "x", "y")


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------

class TestVisibility:
    def test_management_sees_all(self, engine):
        _create(engine)
        wfs = engine.list_workflows("manager1", "management")
        assert len(wfs) == 1

    def test_requester_sees_own(self, engine):
        wf = _create(engine)
        assert [w["id"] for w in engine.list_workflows("client1", "client")] == [wf["id"]]
        # a different client cannot see it
        assert engine.list_workflows("client2", "client") == []

    def test_employee_sees_only_assigned(self, engine):
        wf = _create(engine)
        assert engine.list_workflows("employee1", "employee") == []
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")
        assert [w["id"] for w in engine.list_workflows("employee1", "employee")] == [wf["id"]]
        assert engine.list_workflows("employee2", "employee") == []

    def test_counsel_visible_after_input(self, engine):
        wf = _create(engine)
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")
        assert engine.list_workflows("counsel1", "counsel") == []
        engine.request_input("employee1", "employee", wf["id"],
                             "counsel1", "counsel", "Please review clause 4.")
        assert [w["id"] for w in engine.list_workflows("counsel1", "counsel")] == [wf["id"]]

    def test_get_workflow_permission(self, engine):
        wf = _create(engine)
        with pytest.raises(PermissionError):
            engine.get_workflow(wf["id"], "employee1", "employee")
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")
        got = engine.get_workflow(wf["id"], "employee1", "employee")
        assert got["assigned_to"] == "employee1"

    def test_get_missing(self, engine):
        with pytest.raises(KeyError):
            engine.get_workflow("wf_nope", "manager1", "management")


# ---------------------------------------------------------------------------
# Approval / rejection
# ---------------------------------------------------------------------------

class TestApproval:
    def test_approve_and_assign(self, engine, events):
        wf = _create(engine)
        out = engine.approve_and_assign("manager1", "management", wf["id"],
                                        "employee1", note="Take a look")
        assert out["status"] == ST_ASSIGNED
        assert out["assigned_to"] == "employee1"
        assert out["assigned_by"] == "manager1"
        assert any(a["kind"] == "approved" for a in out["activity"])
        assert events[-1]["type"] == "workflow.assigned"
        assert events[-1]["assigned_to"] == "employee1"

    def test_approve_wrong_state(self, engine):
        wf = _create(engine)
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")
        with pytest.raises(ValueError):
            engine.approve_and_assign("manager1", "management", wf["id"], "employee2")

    @pytest.mark.parametrize("portal", ["client", "employee", "counsel", "auditor"])
    def test_approve_wrong_portal(self, engine, portal):
        wf = _create(engine)
        with pytest.raises(PermissionError):
            engine.approve_and_assign("u1", portal, wf["id"], "employee1")

    def test_reject(self, engine, events):
        wf = _create(engine)
        out = engine.reject("manager1", "management", wf["id"], note="Out of scope")
        assert out["status"] == ST_REJECTED
        assert events[-1]["type"] == "workflow.rejected"
        assert events[-1]["note"] == "Out of scope"

    def test_reject_wrong_state(self, engine):
        wf = _create(engine)
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")
        with pytest.raises(ValueError):
            engine.reject("manager1", "management", wf["id"])


# ---------------------------------------------------------------------------
# Employee work
# ---------------------------------------------------------------------------

class TestWork:
    def _assigned(self, engine, assignee="employee1"):
        wf = _create(engine)
        engine.approve_and_assign("manager1", "management", wf["id"], assignee)
        return wf

    def test_start_work(self, engine, events):
        wf = self._assigned(engine)
        out = engine.start_work("employee1", "employee", wf["id"])
        assert out["status"] == ST_IN_PROGRESS
        assert events[-1]["type"] == "workflow.started"

    def test_start_idempotent(self, engine):
        wf = self._assigned(engine)
        engine.start_work("employee1", "employee", wf["id"])
        out = engine.start_work("employee1", "employee", wf["id"])
        assert out["status"] == ST_IN_PROGRESS

    def test_wrong_employee_cannot_work(self, engine):
        wf = self._assigned(engine, assignee="employee1")
        with pytest.raises(PermissionError):
            engine.start_work("employee2", "employee", wf["id"])

    @pytest.mark.parametrize("portal", ["client", "tenant", "management", "auditor"])
    def test_non_worker_portal_cannot_work(self, engine, portal):
        wf = self._assigned(engine)
        with pytest.raises(PermissionError):
            engine.start_work("employee1", portal, wf["id"])

    def test_add_activity(self, engine, events):
        wf = self._assigned(engine)
        out = engine.add_activity("employee1", "employee", wf["id"],
                                  "note", "Drafted first response.")
        assert out["activity"][-1]["kind"] == "note"
        assert out["activity"][-1]["text"] == "Drafted first response."
        assert events[-1]["type"] == "workflow.activity"
        assert events[-1]["kind"] == "note"

    def test_run_ai_records_result(self, engine, events):
        wf = self._assigned(engine)
        out = engine.run_ai("employee1", "employee", wf["id"],
                            "Summarize the lease obligations.")
        ai_activity = [a for a in out["activity"] if a["kind"] == "ai"]
        assert len(ai_activity) == 1
        assert ai_activity[0]["data"]["answer"] == "AI answer to: Summarize the lease obligations."
        assert ai_activity[0]["data"]["agent_id"] == "agent_2_internal_information"
        assert out["status"] == ST_IN_PROGRESS
        # ai_running then ai_result events
        types = [e["type"] for e in events if e["workflow_id"] == wf["id"]]
        assert "workflow.ai_running" in types
        assert types[-1] == "workflow.ai_result"
        # ai_runner received workflow context
        user, prompt, state = engine._test_ai_calls[-1]
        assert user == "employee1"
        assert state["workflow_id"] == wf["id"]
        assert state["workflow_subject"] == "Lease renewal query"

    def test_run_ai_without_runner(self, tmp_path, bus):
        eng = WorkflowEngine(store_path=str(tmp_path / "w.jsonl"), bus=bus)
        wf = eng.create_workflow("client1", "client", "s", "m")
        eng.approve_and_assign("manager1", "management", wf["id"], "employee1")
        with pytest.raises(RuntimeError):
            eng.run_ai("employee1", "employee", wf["id"], "hi")

    def test_run_ai_error_is_recorded_not_raised(self, tmp_path, bus):
        def bad_runner(user, prompt, state):
            raise RuntimeError("model offline")

        eng = WorkflowEngine(store_path=str(tmp_path / "w.jsonl"), bus=bus,
                             ai_runner=bad_runner)
        wf = eng.create_workflow("client1", "client", "s", "m")
        eng.approve_and_assign("manager1", "management", wf["id"], "employee1")
        out = eng.run_ai("employee1", "employee", wf["id"], "hi")
        ai_activity = [a for a in out["activity"] if a["kind"] == "ai"]
        assert ai_activity[0]["data"]["status"] == "error"
        assert "model offline" in ai_activity[0]["data"]["answer"]


# ---------------------------------------------------------------------------
# Input requests (employee <-> stakeholder)
# ---------------------------------------------------------------------------

class TestInputFlow:
    def _in_progress(self, engine):
        wf = _create(engine)
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")
        engine.start_work("employee1", "employee", wf["id"])
        return wf

    def test_request_and_answer(self, engine, events):
        wf = self._in_progress(engine)
        out = engine.request_input("employee1", "employee", wf["id"],
                                   "client1", "client", "Which unit is affected?")
        assert out["status"] == ST_WAITING_INPUT
        assert out["inputs"][0]["status"] == "pending"
        assert events[-1]["type"] == "workflow.input_requested"
        assert events[-1]["to_portal"] == "client"

        inp_id = out["inputs"][0]["id"]
        out2 = engine.answer_input("client1", "client", inp_id, "Unit 4B")
        assert out2["inputs"][0]["status"] == "answered"
        assert out2["inputs"][0]["answer"] == "Unit 4B"
        # back to in_progress when all inputs answered
        assert out2["status"] == ST_IN_PROGRESS
        assert events[-1]["type"] == "workflow.input_answered"
        assert events[-1]["answer"] == "Unit 4B"

    def test_request_bad_target_portal(self, engine):
        wf = self._in_progress(engine)
        with pytest.raises(PermissionError):
            engine.request_input("employee1", "employee", wf["id"],
                                 "manager1", "management", "q")

    def test_wrong_stakeholder_cannot_answer(self, engine):
        wf = self._in_progress(engine)
        out = engine.request_input("employee1", "employee", wf["id"],
                                   "client1", "client", "q")
        inp_id = out["inputs"][0]["id"]
        with pytest.raises(PermissionError):
            engine.answer_input("client2", "client", inp_id, "nope")

    def test_cannot_answer_twice(self, engine):
        wf = self._in_progress(engine)
        out = engine.request_input("employee1", "employee", wf["id"],
                                   "client1", "client", "q")
        inp_id = out["inputs"][0]["id"]
        engine.answer_input("client1", "client", inp_id, "a")
        with pytest.raises(ValueError):
            engine.answer_input("client1", "client", inp_id, "b")

    def test_unknown_input(self, engine):
        with pytest.raises(KeyError):
            engine.answer_input("client1", "client", "inp_nope", "x")

    def test_stays_waiting_until_all_answered(self, engine):
        wf = self._in_progress(engine)
        out = engine.request_input("employee1", "employee", wf["id"],
                                   "client1", "client", "q1")
        out = engine.request_input("employee1", "employee", wf["id"],
                                   "counsel1", "counsel", "q2")
        assert out["status"] == ST_WAITING_INPUT
        first = [i for i in out["inputs"] if i["question"] == "q1"][0]
        out2 = engine.answer_input("client1", "client", first["id"], "a1")
        # one still pending -> stays waiting
        assert out2["status"] == ST_WAITING_INPUT
        second = [i for i in out2["inputs"] if i["question"] == "q2"][0]
        out3 = engine.answer_input("counsel1", "counsel", second["id"], "a2")
        assert out3["status"] == ST_IN_PROGRESS


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------

class TestCompletion:
    def _in_progress(self, engine):
        wf = _create(engine)
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")
        engine.start_work("employee1", "employee", wf["id"])
        return wf

    def test_complete(self, engine, events):
        wf = self._in_progress(engine)
        out = engine.complete_workflow("employee1", "employee", wf["id"],
                                       "Your lease renews on 1 Apr 2027.")
        assert out["status"] == ST_COMPLETED
        assert out["final_response"] == "Your lease renews on 1 Apr 2027."
        assert out["completed_at"] is not None
        assert events[-1]["type"] == "workflow.completed"
        assert events[-1]["final_response"] == "Your lease renews on 1 Apr 2027."
        # requester can read the final response
        got = engine.get_workflow(wf["id"], "client1", "client")
        assert got["final_response"] == "Your lease renews on 1 Apr 2027."

    def test_non_worker_cannot_complete(self, engine):
        wf = self._in_progress(engine)
        with pytest.raises(PermissionError):
            engine.complete_workflow("client1", "client", wf["id"], "x")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_reload_from_jsonl(self, tmp_path, bus):
        path = str(tmp_path / "w.jsonl")
        eng1 = WorkflowEngine(store_path=path, bus=bus)
        wf = eng1.create_workflow("client1", "client", "s", "m")
        eng1.approve_and_assign("manager1", "management", wf["id"], "employee1")

        eng2 = WorkflowEngine(store_path=path, bus=bus)
        got = eng2.get_workflow(wf["id"], "manager1", "management")
        assert got["status"] == ST_ASSIGNED
        assert got["assigned_to"] == "employee1"
        assert len(got["activity"]) == 2

    def test_stats(self, engine):
        wf = _create(engine)
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")
        s = engine.stats()
        assert s["total"] == 1
        assert s["by_status"] == {ST_ASSIGNED: 1}


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    def test_end_to_end(self, engine, events):
        # 1. client submits
        wf = _create(engine, subject="Lease renewal advice")
        assert engine.stats()["by_status"] == {ST_PENDING_APPROVAL: 1}

        # 2. management approves + assigns
        engine.approve_and_assign("manager1", "management", wf["id"], "employee1")

        # 3. employee starts + uses AI
        engine.start_work("employee1", "employee", wf["id"])
        engine.run_ai("employee1", "employee", wf["id"], "Summarize obligations.")

        # 4. employee requests input from client
        out = engine.request_input("employee1", "employee", wf["id"],
                                   "client1", "client", "Is the tenant staying?")
        inp_id = out["inputs"][0]["id"]

        # 5. client answers live
        engine.answer_input("client1", "client", inp_id, "Yes, staying 2 more years")

        # 6. employee completes
        engine.complete_workflow("employee1", "employee", wf["id"],
                                 "Renewal confirmed for 2 years at current rates.")

        final = engine.get_workflow(wf["id"], "client1", "client")
        assert final["status"] == ST_COMPLETED
        assert final["final_response"] == "Renewal confirmed for 2 years at current rates."
        assert final["inputs"][0]["answer"] == "Yes, staying 2 more years"

        # every state change produced an event
        types = [e["type"] for e in events]
        for expected in (
            "workflow.created", "workflow.assigned", "workflow.started",
            "workflow.ai_running", "workflow.ai_result",
            "workflow.input_requested", "workflow.input_answered",
            "workflow.completed",
        ):
            assert expected in types, f"missing event {expected}"