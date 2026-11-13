"""Propositions and inference rules used by the diagnosis application."""

from logic_engine import Rule, parse_formula


PROPOSITIONS = [
    {"symbol": "P", "name": "Power supply available", "category": "Supply"},
    {"symbol": "M", "name": "Main switch ON", "category": "Controls"},
    {"symbol": "F", "name": "Fuse healthy", "category": "Protection"},
    {"symbol": "W", "name": "Wiring healthy", "category": "Wiring"},
    {"symbol": "B", "name": "Bulb healthy", "category": "Lighting"},
    {"symbol": "L", "name": "Light functioning", "category": "Lighting"},
    {"symbol": "S", "name": "Socket functioning", "category": "Outlets"},
    {"symbol": "A", "name": "Appliance functioning", "category": "Appliances"},
    {"symbol": "C", "name": "Circuit breaker ON", "category": "Protection"},
    {"symbol": "O", "name": "Overload detected", "category": "Protection"},
    {"symbol": "E", "name": "Electrical connection healthy", "category": "Wiring"},
]

PROPOSITION_BY_SYMBOL = {item["symbol"]: item for item in PROPOSITIONS}

_RULE_DATA = [
    ("R1", "P ∧ M ∧ F ∧ W ∧ B → L",
     "Available power, an ON main switch, a healthy fuse and wiring, and a healthy bulb imply a functioning light."),
    ("R2", "P ∧ M ∧ F ∧ W ∧ E → S",
     "Power, the main switch, fuse, wiring, and electrical connection imply a functioning socket."),
    ("R3", "P ∧ C ∧ F ∧ W ∧ E → A",
     "Power, an ON breaker, fuse, wiring, and electrical connection imply a functioning appliance."),
    ("R4", "O → ¬C",
     "A detected overload implies that the circuit breaker is not ON (it may have tripped)."),
    ("R5", "¬P → ¬L", "Without an available power supply, the light does not function."),
    ("R6", "¬M → ¬L", "With the main switch OFF, the light does not function."),
    ("R7", "¬F → ¬L", "With a blown/unhealthy fuse, the light does not function."),
    ("R8", "¬W → ¬L", "With faulty wiring, the light does not function."),
    ("R9", "¬B → ¬L", "With a faulty bulb, the light does not function."),
    ("R10", "¬E → ¬S", "With an unhealthy electrical connection, the socket does not function."),
    ("R11", "¬P → ¬S", "Without an available power supply, the socket does not function."),
    ("R12", "¬P → ¬A", "Without an available power supply, the appliance does not function."),
    ("R13", "¬C → ¬A", "With the circuit breaker OFF, the appliance does not function."),
    ("R14", "¬F → ¬S", "With a blown/unhealthy fuse, the socket does not function."),
    ("R15", "¬W → ¬S", "With faulty wiring, the socket does not function."),
    ("R16", "¬F → ¬A", "With a blown/unhealthy fuse, the appliance does not function."),
    ("R17", "¬W → ¬A", "With faulty wiring, the appliance does not function."),
    ("R18", "¬E → ¬A", "With an unhealthy electrical connection, the appliance does not function."),
]

RULES = [
    Rule(
        identifier=identifier,
        formula=parse_formula(symbolic),
        description=description,
        conclusion=parse_formula(symbolic.rsplit("→", 1)[1].strip()),
    )
    for identifier, symbolic, description in _RULE_DATA
]

RULE_BY_ID = {rule.identifier: rule for rule in RULES}
