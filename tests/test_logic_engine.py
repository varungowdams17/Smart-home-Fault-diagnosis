import unittest

from knowledge_base import PROPOSITIONS, RULES
from logic_engine import (
    backward_chain,
    entailment,
    forward_chain,
    models,
    parse_formula,
)


SYMBOLS = [item["symbol"] for item in PROPOSITIONS]


class LogicEngineTests(unittest.TestCase):
    def test_parser_supports_all_operators_and_precedence(self):
        formula = parse_formula("P ∧ M → L ∨ ¬B")
        self.assertEqual(formula.evaluate({"P": True, "M": True, "L": False, "B": False}), True)
        self.assertEqual(formula.evaluate({"P": True, "M": True, "L": False, "B": True}), False)

    def test_forward_chaining_derives_healthy_light(self):
        facts = {"P": True, "M": True, "F": True, "W": True, "B": True}
        result = forward_chain(facts, RULES)
        self.assertTrue(result.consistent)
        self.assertIs(result.derived["L"], True)
        self.assertEqual(result.steps[0]["rule_id"], "R1")

    def test_backward_chaining_proves_light_from_conditions(self):
        facts = {"P": True, "M": True, "F": True, "W": True, "B": True}
        result = backward_chain(parse_formula("L"), RULES, facts)
        self.assertTrue(result["proven"])
        self.assertEqual(result["steps"][-1]["rule_id"], "R1")

    def test_symptom_does_not_entail_specific_unknown_fault(self):
        facts = {"P": True, "M": True, "L": False}
        result = entailment(parse_formula("¬F"), RULES, facts, SYMBOLS)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertGreater(len(models(RULES, facts, SYMBOLS)), 0)

    def test_supply_failure_entails_nonfunctioning_light(self):
        result = entailment(parse_formula("¬L"), RULES, {"P": False}, SYMBOLS)
        self.assertEqual(result["status"], "TRUE")

    def test_inconsistent_observations_are_detected(self):
        facts = {"P": True, "M": True, "F": True, "W": True, "B": True, "L": False}
        result = entailment(parse_formula("L"), RULES, facts, SYMBOLS)
        self.assertEqual(result["status"], "INCONSISTENT")


if __name__ == "__main__":
    unittest.main()
