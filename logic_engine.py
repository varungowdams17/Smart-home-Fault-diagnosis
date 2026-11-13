"""Small propositional-logic engine for the smart-home diagnosis simulator."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


Token = Tuple[str, str]


class FormulaError(ValueError):
    """Raised when a propositional formula cannot be parsed."""


@dataclass(frozen=True)
class Formula:
    operator: str
    value: Optional[str] = None
    left: Optional["Formula"] = None
    right: Optional["Formula"] = None

    def symbols(self) -> Set[str]:
        if self.operator == "symbol":
            return {self.value or ""}
        found: Set[str] = set()
        if self.left:
            found.update(self.left.symbols())
        if self.right:
            found.update(self.right.symbols())
        return found

    def evaluate(self, assignment: Mapping[str, bool]) -> bool:
        if self.operator == "symbol":
            return bool(assignment[self.value or ""])
        if self.operator == "not":
            return not self.left.evaluate(assignment)  # type: ignore[union-attr]
        if self.operator == "and":
            return self.left.evaluate(assignment) and self.right.evaluate(assignment)  # type: ignore[union-attr]
        if self.operator == "or":
            return self.left.evaluate(assignment) or self.right.evaluate(assignment)  # type: ignore[union-attr]
        if self.operator == "implies":
            return not self.left.evaluate(assignment) or self.right.evaluate(assignment)  # type: ignore[union-attr]
        raise FormulaError(f"Unknown operator: {self.operator}")

    def evaluate_partial(self, facts: Mapping[str, bool]) -> Optional[bool]:
        """Kleene three-valued evaluation; None means the result is not known."""
        if self.operator == "symbol":
            return facts.get(self.value or "")
        left = self.left.evaluate_partial(facts) if self.left else None
        if self.operator == "not":
            return None if left is None else not left
        right = self.right.evaluate_partial(facts) if self.right else None
        if self.operator == "and":
            if left is False or right is False:
                return False
            return True if left is True and right is True else None
        if self.operator == "or":
            if left is True or right is True:
                return True
            return False if left is False and right is False else None
        if self.operator == "implies":
            if left is False or right is True:
                return True
            if left is True and right is False:
                return False
            return None
        raise FormulaError(f"Unknown operator: {self.operator}")

    def __str__(self) -> str:
        if self.operator == "symbol":
            return self.value or ""
        if self.operator == "not":
            return f"¬{self.left}"
        symbol = {"and": "∧", "or": "∨", "implies": "→"}[self.operator]
        return f"({self.left} {symbol} {self.right})"


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    while i < len(source):
        if source[i].isspace():
            i += 1
            continue
        char = source[i]
        if char in "()":
            tokens.append((char, char))
            i += 1
            continue
        if char in "∧∨¬":
            tokens.append((char, char))
            i += 1
            continue
        if source[i:i + 2] == "->":
            tokens.append(("→", "→"))
            i += 2
            continue
        if char == "→":
            tokens.append(("→", "→"))
            i += 1
            continue
        if char.isalpha() and char.isupper():
            start = i
            i += 1
            while i < len(source) and source[i].isalnum() and source[i].isupper():
                i += 1
            tokens.append(("symbol", source[start:i]))
            continue
        raise FormulaError(f"Unexpected character at position {i}: {char!r}")
    return tokens


class _Parser:
    def __init__(self, tokens: Sequence[Token]):
        self.tokens = tokens
        self.position = 0

    def parse(self) -> Formula:
        result = self.implication()
        if self.position != len(self.tokens):
            raise FormulaError("Unexpected token after formula.")
        return result

    def implication(self) -> Formula:
        left = self.disjunction()
        if self._accept("→"):
            return Formula("implies", left=left, right=self.implication())
        return left

    def disjunction(self) -> Formula:
        result = self.conjunction()
        while self._accept("∨"):
            result = Formula("or", left=result, right=self.conjunction())
        return result

    def conjunction(self) -> Formula:
        result = self.negation()
        while self._accept("∧"):
            result = Formula("and", left=result, right=self.negation())
        return result

    def negation(self) -> Formula:
        if self._accept("¬"):
            return Formula("not", left=self.negation())
        if self._accept("("):
            result = self.implication()
            if not self._accept(")"):
                raise FormulaError("Missing closing parenthesis.")
            return result
        if self.position < len(self.tokens) and self.tokens[self.position][0] == "symbol":
            value = self.tokens[self.position][1]
            self.position += 1
            return Formula("symbol", value=value)
        raise FormulaError("Expected a proposition, negation, or parenthesized expression.")

    def _accept(self, kind: str) -> bool:
        if self.position < len(self.tokens) and self.tokens[self.position][0] == kind:
            self.position += 1
            return True
        return False


def parse_formula(source: str) -> Formula:
    if not source.strip():
        raise FormulaError("Formula cannot be empty.")
    return _Parser(tokenize(source)).parse()


@dataclass(frozen=True)
class Rule:
    identifier: str
    formula: Formula
    description: str
    conclusion: Formula


@dataclass
class InferenceResult:
    facts: Dict[str, bool]
    derived: Dict[str, bool]
    steps: List[dict]
    consistent: bool


def _literal(formula: Formula) -> Optional[Tuple[str, bool]]:
    if formula.operator == "symbol":
        return formula.value or "", True
    if formula.operator == "not" and formula.left and formula.left.operator == "symbol":
        return formula.left.value or "", False
    return None


def forward_chain(observations: Mapping[str, bool], rules: Sequence[Rule]) -> InferenceResult:
    facts = dict(observations)
    derived: Dict[str, bool] = {}
    steps: List[dict] = []
    consistent = True
    fired_rules: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for rule in rules:
            if rule.identifier in fired_rules:
                continue
            premise = rule.formula.left
            conclusion = rule.conclusion
            if premise is None or premise.evaluate_partial(facts) is not True:
                continue
            literal = _literal(conclusion)
            if not literal:
                continue
            fired_rules.add(rule.identifier)
            symbol, value = literal
            if symbol in facts:
                if facts[symbol] != value:
                    consistent = False
                    steps.append({
                        "rule_id": rule.identifier,
                        "rule": str(rule.formula),
                        "description": rule.description,
                        "conclusion": f"{'¬' if not value else ''}{symbol}",
                        "conflict": True,
                        "text": f"{rule.identifier} conflicts with the observed value of {symbol}: the rule supports "
                                f"{'¬' if not value else ''}{symbol}, but the observation states "
                                f"{'¬' if not facts[symbol] else ''}{symbol}.",
                    })
                else:
                    steps.append({
                        "rule_id": rule.identifier,
                        "rule": str(rule.formula),
                        "description": rule.description,
                        "conclusion": f"{'¬' if not value else ''}{symbol}",
                        "text": f"{rule.identifier} supports the observed fact: {rule.description}",
                    })
                continue
            facts[symbol] = value
            derived[symbol] = value
            changed = True
            steps.append({
                "rule_id": rule.identifier,
                "rule": str(rule.formula),
                "description": rule.description,
                "conclusion": f"{'¬' if not value else ''}{symbol}",
                "text": f"{rule.identifier} applies: {rule.description}",
            })
    for symbol, value in observations.items():
        if symbol in derived and derived[symbol] != value:
            consistent = False
    return InferenceResult(dict(observations), derived, steps, consistent)


def models(
    rules: Sequence[Rule],
    observations: Mapping[str, bool],
    symbols: Iterable[str],
) -> List[Dict[str, bool]]:
    """Enumerate all models satisfying the rules and observations."""
    ordered = sorted(set(symbols) | set(observations))
    result: List[Dict[str, bool]] = []
    for values in product((False, True), repeat=len(ordered)):
        assignment = dict(zip(ordered, values))
        if any(assignment[symbol] != value for symbol, value in observations.items()):
            continue
        if all(rule.formula.evaluate(assignment) for rule in rules):
            result.append(assignment)
    return result


def entailment(
    query: Formula,
    rules: Sequence[Rule],
    observations: Mapping[str, bool],
    symbols: Iterable[str],
) -> dict:
    query_symbols = query.symbols()
    all_symbols = set(symbols) | query_symbols | set(observations)
    possible = models(rules, observations, all_symbols)
    if not possible:
        return {"status": "INCONSISTENT", "models": 0, "support": [], "refutation": []}
    supporting = [model for model in possible if query.evaluate(model)]
    refuting = [model for model in possible if not query.evaluate(model)]
    status = "TRUE" if not refuting else "FALSE" if not supporting else "UNKNOWN"
    return {
        "status": status,
        "models": len(possible),
        "support": supporting[:3],
        "refutation": refuting[:3],
    }


def backward_chain(
    query: Formula, rules: Sequence[Rule], known: Mapping[str, bool]
) -> dict:
    """Prove a literal goal recursively using facts and modus ponens rules."""
    goal = _literal(query)
    visited: Set[Tuple[str, bool]] = set()
    proof: List[dict] = []

    def prove(literal: Tuple[str, bool]) -> bool:
        symbol, value = literal
        if symbol in known:
            return known[symbol] == value
        if literal in visited:
            return False
        visited.add(literal)
        for rule in rules:
            if _literal(rule.conclusion) != literal or rule.formula.left is None:
                continue
            premises = _conjunctive_literals(rule.formula.left)
            if premises is not None and all(prove(item) for item in premises):
                proof.append({
                    "rule_id": rule.identifier,
                    "rule": str(rule.formula),
                    "description": rule.description,
                    "conclusion": str(query),
                })
                return True
        return False

    result = prove(goal) if goal else False
    return {"proven": result, "steps": proof}


def _conjunctive_literals(formula: Formula) -> Optional[List[Tuple[str, bool]]]:
    if formula.operator == "and":
        left = _conjunctive_literals(formula.left)  # type: ignore[arg-type]
        right = _conjunctive_literals(formula.right)  # type: ignore[arg-type]
        return left + right if left is not None and right is not None else None
    literal = _literal(formula)
    return [literal] if literal else None
