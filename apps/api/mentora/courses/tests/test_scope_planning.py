"""Planner 资料范围校验与清洗。"""

from django.test import SimpleTestCase

from mentora.courses.scope_planning import (
    collect_plan_evidence_ids,
    sanitize_plan_evidence_ids,
    validate_plan_evidence_ids,
)


class ScopePlanningTests(SimpleTestCase):
    def test_sanitize_plan_evidence_ids_removes_out_of_scope(self):
        allowed = {"ev-1", "ev-2"}
        plan = {
            "phases": [{
                "units": [{
                    "source_evidence_ids": ["ev-1", "ev-9", "evidence_id=ev-2"],
                    "tasks": [{
                        "source_evidence_ids": ["ev-3"],
                    }],
                }],
            }],
            "topics": [{
                "evidence_ids": ["ev-1", "bad-id"],
            }],
        }

        removed = sanitize_plan_evidence_ids(plan, allowed)

        self.assertEqual(removed, ["bad-id", "ev-3", "ev-9"])
        self.assertEqual(plan["topics"][0]["evidence_ids"], ["ev-1"])
        self.assertEqual(plan["phases"][0]["units"][0]["source_evidence_ids"], ["ev-1", "ev-2"])
        self.assertEqual(plan["phases"][0]["units"][0]["tasks"][0]["source_evidence_ids"], [])
        self.assertEqual(validate_plan_evidence_ids(plan, allowed), [])

    def test_collect_plan_evidence_ids_normalizes_prompt_prefix(self):
        plan = {
            "topics": [{"evidence_ids": ["evidence_id=abc-123"]}],
            "phases": [],
        }
        self.assertEqual(collect_plan_evidence_ids(plan), {"abc-123"})
