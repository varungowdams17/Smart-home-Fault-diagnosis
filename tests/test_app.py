import os
import tempfile
import unittest
from pathlib import Path

import app as application


class FlaskApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        application.DATABASE = Path(os.path.join(self.temp_dir.name, "test.db"))
        application.initialize_database()
        self.client = application.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dashboard_and_navigation_pages_render(self):
        for path in ("/", "/diagnosis", "/knowledge-base", "/rules", "/reasoning", "/history", "/about"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_diagnosis_keeps_possible_causes_unproven(self):
        response = self.client.post("/api/diagnose", json={
            "power": "available", "main_switch": "on", "symptoms": ["light_not_working"],
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["consistent"])
        self.assertTrue(data["causes"])
        self.assertTrue(all(cause["certainty"] == "possible" for cause in data["causes"]))
        self.assertFalse(any(fact["symbol"] == "F" for fact in data["derived"]))

    def test_observed_blown_fuse_proves_light_failure(self):
        response = self.client.post("/api/scenario/1", json={})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["consistent"])
        self.assertTrue(any(step.get("rule_id") == "R7" for step in data["steps"]))
        self.assertTrue(any(cause["symbol"] == "F" and cause["certainty"] == "observed" for cause in data["causes"]))

    def test_all_reasoning_scenarios_produce_expected_results(self):
        power_failure = self.client.post("/api/scenario/2", json={}).get_json()
        self.assertIn("P", [cause["symbol"] for cause in power_failure["causes"]])
        self.assertTrue(any(step.get("rule_id") == "R5" for step in power_failure["steps"]))

        bulb_failure = self.client.post("/api/scenario/3", json={}).get_json()
        self.assertTrue(any(step.get("rule_id") == "R9" for step in bulb_failure["steps"]))
        self.assertTrue(any(cause["symbol"] == "B" and cause["certainty"] == "observed" for cause in bulb_failure["causes"]))

        healthy_light = self.client.post("/api/scenario/4", json={}).get_json()
        self.assertTrue(any(item["symbol"] == "L" and item["value"] is True for item in healthy_light["derived"]))

        multiple_causes = self.client.post("/api/scenario/5", json={}).get_json()
        self.assertEqual(
            {cause["symbol"] for cause in multiple_causes["causes"]},
            {"F", "W", "B"},
        )
        self.assertTrue(all(cause["certainty"] == "possible" for cause in multiple_causes["causes"]))

    def test_entailment_returns_unknown_for_unobserved_supply(self):
        response = self.client.post("/api/entailment", json={"query": "P"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "UNKNOWN")

    def test_entailment_rejects_unknown_symbols(self):
        response = self.client.post("/api/entailment", json={"query": "Z"})
        self.assertEqual(response.status_code, 400)

    def test_conflicting_rule_and_symptom_are_reported_without_conclusions(self):
        response = self.client.post("/api/diagnose", json={
            "power": "available",
            "main_switch": "on",
            "fuse": "healthy",
            "wiring": "healthy",
            "bulb": "healthy",
            "symptoms": ["light_not_working"],
        })
        data = response.get_json()
        self.assertFalse(data["consistent"])
        self.assertEqual(data["derived"], [])
        self.assertTrue(any(step.get("kind") == "warning" and step.get("rule_id") == "R1" for step in data["steps"]))

    def test_diagnosis_is_persisted_to_history(self):
        self.client.post("/api/diagnose", json={"power": "unavailable"})
        response = self.client.get("/history")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Power supply: unavailable", response.data)


if __name__ == "__main__":
    unittest.main()
