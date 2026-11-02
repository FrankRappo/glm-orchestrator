#!/usr/bin/env python3
import importlib.util
import io
import json
from pathlib import Path
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("quota_monitor", HERE.parent / "quota_monitor.py")
quota = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(quota)


class QuotaMonitorTests(unittest.TestCase):
    def test_owner_policy_removes_reserve_from_older_glm_callers_only(self):
        self.assertEqual(0.0, quota.effective_reserve_percent("zcode", 15.0))
        self.assertEqual(15.0, quota.effective_reserve_percent("codex", 15.0))

    def test_zero_reserve_uses_remaining_budget_but_stops_at_actual_exhaustion(self):
        now = int(quota.time.time())
        buckets = [{"provider": "zcode", "kind": "coding_plan", "model": None,
                    "used_percent": 88, "remaining": 15770, "limit": 140000,
                    "observed_at": now}]
        self.assertEqual("allow", quota.admission(buckets, "zcode", "GLM-5.3-Flash", 0, 60)["decision"])
        buckets[0].update(used_percent=99, remaining=0)
        result = quota.admission(buckets, "zcode", "GLM-5.3-Flash", 0, 60)
        self.assertEqual(("deny", "quota_exhausted"), (result["decision"], result["reason"]))

    def test_zero_reserve_does_not_bypass_unknown_or_stale_quota(self):
        self.assertEqual("unknown", quota.admission([], "zcode", "GLM-5.3-Flash", 0, 60)["decision"])
        buckets = [{"provider": "zcode", "kind": "coding_plan", "used_percent": 10,
                    "observed_at": int(quota.time.time()) - 120}]
        result = quota.admission(buckets, "zcode", "GLM-5.3-Flash", 0, 60)
        self.assertEqual(("unknown", "quota_snapshot_stale"), (result["decision"], result["reason"]))

    def test_remaining_percent_in_human_and_json_output(self):
        buckets = [
            {"provider": "zcode", "kind": "coding_plan", "name": "five_hour", "window": "five_hour",
             "used_percent": 8, "remaining": 25702, "limit": 28000, "status": "ok"},
            {"provider": "zcode", "kind": "coding_plan", "name": "weekly", "window": "weekly",
             "used_percent": 10, "remaining": 125235, "limit": 140000, "status": "ok"},
        ]
        with patch.object(quota, "newest_files", return_value=[]), \
             patch.object(quota, "parse_zcode", return_value=(buckets, [])), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, quota.main(["--provider", "zcode", "--no-live-zcode", "--json"]))
        reported = {item["name"]: item for item in json.loads(output.getvalue())["buckets"]}
        self.assertEqual(91.79, reported["five_hour"]["remaining_percent"])
        self.assertEqual(89.45, reported["weekly"]["remaining_percent"])
        human = quota.human({"generated_at": 0, "plans": [], "buckets": list(reported.values())})
        self.assertIn("remaining_pct= 91.79%", human)
        self.assertIn("remaining_pct= 89.45%", human)

    def test_zero_limit_does_not_invent_remaining_percent(self):
        bucket = {"provider": "zcode", "name": "empty", "window": "daily", "used_percent": 0,
                  "remaining": 0, "limit": 0, "status": "ok"}
        self.assertIsNone(quota.remaining_percent(bucket))
        human = quota.human({"generated_at": 0, "plans": [], "buckets": [bucket]})
        self.assertIn("remaining_pct=   n/a", human)

    def test_zcode_buckets_and_admission(self):
        buckets, plans = quota.parse_zcode([HERE / "fixtures" / "zcode.txt"])
        self.assertEqual("Test Plan", plans[0]["name"])
        self.assertTrue(any(plan.get("level") == "max" for plan in plans))
        by_name = {item["name"]: item for item in buckets}
        self.assertEqual(20.0, by_name["GLM-5.3"]["used_percent"])
        self.assertEqual("critical", by_name["GLM-5.3-Flash"]["status"])
        decision = quota.admission(buckets, "zcode", "GLM-5.3-Flash", 15, 10**9)
        self.assertEqual("deny", decision["decision"])

    def test_codex_window_names(self):
        buckets = quota.parse_codex([HERE / "fixtures" / "codex.jsonl"])
        by_window = {item["window"]: item for item in buckets}
        self.assertEqual(40.0, by_window["five_hour"]["used_percent"])
        self.assertEqual("warning", by_window["weekly"]["status"])

    def test_any_usable_zcode_bucket_admits_same_model(self):
        now = int(quota.time.time())
        buckets = [
            {"provider": "zcode", "model": "GLM-5.3-Flash", "used_percent": 99, "observed_at": now},
            {"provider": "zcode", "model": "GLM-5.3-Flash", "used_percent": 10, "observed_at": now},
        ]
        decision = quota.admission(buckets, "zcode", "GLM-5.3-Flash", 15, 10**9)
        self.assertEqual("allow", decision["decision"])

    def test_any_exhausted_coding_plan_window_denies(self):
        now = int(quota.time.time())
        buckets = [
            {"provider": "zcode", "kind": "coding_plan", "model": None, "used_percent": 90, "observed_at": now},
            {"provider": "zcode", "kind": "coding_plan", "model": None, "used_percent": 10, "observed_at": now},
        ]
        decision = quota.admission(buckets, "zcode", "GLM-5.3", 15, 10**9)
        self.assertEqual("deny", decision["decision"])


if __name__ == "__main__":
    unittest.main()
