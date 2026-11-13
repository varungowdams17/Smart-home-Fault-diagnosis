"""Flask application for educational smart-home fault diagnosis."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Tuple

from flask import Flask, jsonify, render_template, request

from knowledge_base import PROPOSITIONS, PROPOSITION_BY_SYMBOL, RULES
from logic_engine import FormulaError, backward_chain, entailment, forward_chain, models, parse_formula


ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("SMART_HOME_DB", ROOT / "database.db"))
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

INPUT_FIELDS = {
    "power": ("P", {"available": True, "unavailable": False}),
    "main_switch": ("M", {"on": True, "off": False}),
    "fuse": ("F", {"healthy": True, "blown": False}),
    "wiring": ("W", {"healthy": True, "faulty": False}),
    "bulb": ("B", {"healthy": True, "faulty": False}),
    "breaker": ("C", {"on": True, "off": False}),
    "overload": ("O", {"detected": True, "clear": False}),
    "connection": ("E", {"healthy": True, "faulty": False}),
}

SYMPTOMS = {
    "light_not_working": ("L", False, "Light not working"),
    "socket_not_working": ("S", False, "Socket not working"),
    "appliance_not_working": ("A", False, "Appliance not working"),
    "house_no_power": ("P", False, "Entire house has no power"),
    "breaker_trips": ("O", True, "Circuit breaker frequently trips"),
}

SYSTEMS = {
    "L": {
        "name": "Light",
        "inputs": ("P", "M", "F", "W", "B"),
        "fault_rules": {"P": "R5", "M": "R6", "F": "R7", "W": "R8", "B": "R9"},
    },
    "S": {
        "name": "Socket",
        "inputs": ("P", "M", "F", "W", "E"),
        "fault_rules": {"P": "R11", "F": "R14", "W": "R15", "E": "R10"},
    },
    "A": {
        "name": "Appliance",
        "inputs": ("P", "C", "F", "W", "E"),
        "fault_rules": {"P": "R12", "C": "R13", "F": "R16", "W": "R17", "E": "R18"},
    },
}

FIELD_LABELS = {
    "P": ("Power supply", "available", "unavailable"),
    "M": ("Main switch", "ON", "OFF"),
    "F": ("Fuse", "healthy", "blown / unhealthy"),
    "W": ("Wiring", "healthy", "faulty"),
    "B": ("Bulb", "healthy", "faulty"),
    "L": ("Light", "functioning", "not functioning"),
    "S": ("Socket", "functioning", "not functioning"),
    "A": ("Appliance", "functioning", "not functioning"),
    "C": ("Circuit breaker", "ON", "OFF"),
    "O": ("Overload", "detected", "not detected"),
    "E": ("Electrical connection", "healthy", "faulty"),
}


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS diagnoses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                observations TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                possible_causes TEXT NOT NULL,
                explanation TEXT NOT NULL
            )"""
        )


initialize_database()


def _read_observations(payload: Mapping) -> Tuple[Dict[str, bool], List[str], List[str]]:
    observations: Dict[str, bool] = {}
    labels: List[str] = []
    errors: List[str] = []
    for field, (symbol, choices) in INPUT_FIELDS.items():
        value = payload.get(field, "unknown")
        if value in ("", None):
            value = "unknown"
        if value == "unknown":
            continue
        if value not in choices:
            errors.append(f"Invalid value for {field}.")
            continue
        observations[symbol] = choices[value]
        labels.append(_fact_label(symbol, choices[value]))

    symptoms = payload.get("symptoms", [])
    if isinstance(symptoms, str):
        symptoms = [symptoms]
    if not isinstance(symptoms, list):
        errors.append("Symptoms must be provided as a list.")
        symptoms = []
    for symptom in symptoms:
        if symptom not in SYMPTOMS:
            errors.append("An unrecognized symptom was selected.")
            continue
        symbol, value, label = SYMPTOMS[symptom]
        if symbol in observations and observations[symbol] != value:
            errors.append(f"Conflicting observations for {PROPOSITION_BY_SYMBOL[symbol]['name']}.")
            continue
        observations[symbol] = value
        labels.append(label)
    return observations, labels, errors


def _fact_label(symbol: str, value: bool) -> str:
    name, positive, negative = FIELD_LABELS[symbol]
    return f"{name}: {positive if value else negative}"


def _literal_formula(symbol: str, value: bool):
    return parse_formula(symbol if value else f"¬{symbol}")


def _diagnose(observations: Dict[str, bool], observed_labels: List[str]) -> dict:
    chained = forward_chain(observations, RULES)
    all_symbols = [item["symbol"] for item in PROPOSITIONS]
    model_set = models(RULES, observations, all_symbols)
    consistent = bool(model_set) and chained.consistent

    if not consistent:
        status_text = "Contradictory observations"
        summary = "The observations conflict with each other or with the knowledge-base rules. Review the selected statuses."
        causes: List[dict] = []
        final_conclusions: List[dict] = []
    else:
        causes = _possible_causes(observations)
        final_conclusions = [
            {"symbol": symbol, "name": PROPOSITION_BY_SYMBOL[symbol]["name"], "value": value,
             "status": "proven"}
            for symbol, value in chained.derived.items()
        ]
        failure_targets = [symbol for symbol in ("L", "S", "A") if observations.get(symbol) is False]
        if failure_targets:
            names = ", ".join(SYSTEMS[symbol]["name"].lower() for symbol in failure_targets)
            proven_causes = [
                cause["name"] for cause in causes
                if cause["target"] in failure_targets and cause["certainty"] == "observed"
            ]
            if proven_causes:
                cause_names = ", ".join(proven_causes)
                summary = f"Observed {cause_names}; the rule base supports the reported {names} failure."
                status_text = "Failure supported by observed fault"
            else:
                summary = f"Observed failure: {names}. Review the possible explanations; no specific cause is proven."
                status_text = "Fault indicators observed"
        elif chained.derived:
            proven = ", ".join(
                f"{PROPOSITION_BY_SYMBOL[symbol]['name']} = {'true' if value else 'false'}"
                for symbol, value in chained.derived.items()
            )
            status_text = "Inference completed"
            summary = f"Rules derive: {proven}. No specific failure symptom was reported."
        elif observations:
            status_text = "Insufficient evidence"
            summary = "The current observations do not prove an outcome or a specific fault. Record more conditions to narrow the diagnosis."
        else:
            status_text = "No observations"
            summary = "Select observed conditions or symptoms to run the logic engine."

    steps = []
    for label in observed_labels:
        steps.append({"kind": "observation", "title": "Observed fact", "text": label})
    for step in chained.steps:
        steps.append({
            "kind": "warning" if step.get("conflict") else "inference",
            "title": f"Rule {step['rule_id']}{' conflict' if step.get('conflict') else ''}",
            "text": step["text"],
            "formula": step["rule"],
            "conclusion": step["conclusion"],
            "rule_id": step["rule_id"],
        })

    if consistent:
        for symbol in ("L", "S", "A"):
            if observations.get(symbol) is not False:
                continue
            system = SYSTEMS[symbol]
            known_causes = [cause for cause in causes if cause["target"] == symbol and cause["certainty"] == "observed"]
            if known_causes:
                steps.append({
                    "kind": "explanation",
                    "title": f"Explaining {system['name'].lower()} failure",
                    "text": "The observed unhealthy component matches an implication rule for this failure; the rule proves the failure from that observation.",
                })
            else:
                unknowns = [
                    PROPOSITION_BY_SYMBOL[item]["name"].lower()
                    for item in system["inputs"]
                    if item not in observations
                ]
                if unknowns:
                    steps.append({
                        "kind": "explanation",
                        "title": f"Possible causes for {system['name'].lower()} failure",
                        "text": "The failure is observed, but it does not logically identify one cause. "
                                f"Unobserved relevant conditions include: {', '.join(unknowns)}. "
                                "Each is shown only as a possible explanation.",
                    })
        if not steps:
            steps.append({"kind": "explanation", "title": "No rule fired",
                          "text": "No rule antecedent is fully supported by known facts. Unknown conditions were not treated as false."})
    else:
        steps.append({"kind": "warning", "title": "Consistency check",
                      "text": "No model satisfies all entered observations and rules, so no classical conclusions or causes are reported."})

    return {
        "status": status_text,
        "summary": summary,
        "observations": [
            {"symbol": symbol, "name": PROPOSITION_BY_SYMBOL[symbol]["name"], "value": value,
             "label": _fact_label(symbol, value)}
            for symbol, value in observations.items()
        ],
        "derived": [
            {"symbol": symbol, "name": PROPOSITION_BY_SYMBOL[symbol]["name"], "value": value}
            for symbol, value in (chained.derived.items() if consistent else [])
        ],
        "causes": causes,
        "steps": steps,
        "consistent": consistent,
        "models": len(model_set),
    }


def _possible_causes(observations: Mapping[str, bool]) -> List[dict]:
    causes: List[dict] = []
    for target, system in SYSTEMS.items():
        if observations.get(target) is not False:
            continue
        for input_symbol in system["inputs"]:
            rule_id = system["fault_rules"].get(input_symbol)
            if not rule_id:
                continue
            fault_value = observations.get(input_symbol)
            if fault_value is False:
                causes.append({
                    "target": target, "symbol": input_symbol,
                    "name": _fault_name(input_symbol), "certainty": "observed",
                    "rule_id": rule_id, "rule": str(next(rule.formula for rule in RULES if rule.identifier == rule_id)),
                    "explanation": f"The fault is directly observed and {rule_id} entails the reported failure.",
                })
            elif fault_value is None:
                assumption = dict(observations)
                assumption[input_symbol] = False
                if models(RULES, assumption, [item["symbol"] for item in PROPOSITIONS]):
                    causes.append({
                        "target": target, "symbol": input_symbol,
                        "name": _fault_name(input_symbol), "certainty": "possible",
                        "rule_id": rule_id, "rule": str(next(rule.formula for rule in RULES if rule.identifier == rule_id)),
                        "explanation": f"{rule_id} allows this condition to explain the observed failure, but it is not established by the evidence.",
                    })
    return causes


def _fault_name(symbol: str) -> str:
    names = {
        "P": "Power supply unavailable",
        "M": "Main switch OFF",
        "F": "Fuse unhealthy / blown",
        "W": "Wiring faulty",
        "B": "Bulb faulty",
        "C": "Circuit breaker OFF",
        "E": "Electrical connection faulty",
    }
    return names[symbol]


def _save_diagnosis(result: dict) -> int:
    created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    diagnosis = f"{result['status']}: {result['summary']}"
    with get_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO diagnoses (created_at, observations, diagnosis, possible_causes, explanation)
               VALUES (?, ?, ?, ?, ?)""",
            (
                created_at,
                json.dumps(result["observations"]),
                diagnosis,
                json.dumps(result["causes"]),
                json.dumps(result["steps"]),
            ),
        )
        return int(cursor.lastrowid)


@app.get("/")
def dashboard():
    cards = [
        ("P", "POWER SUPPLY", "ϟ", "icon-blue"),
        ("M", "MAIN SWITCH", "⏻", "icon-violet"),
        ("F", "FUSE", "▣", "icon-amber"),
        ("W", "WIRING", "⌁", "icon-cyan"),
        ("B", "BULB", "☼", "icon-yellow"),
        ("L", "LIGHT", "◉", "icon-green"),
        ("S", "SOCKET", "▤", "icon-pink"),
        ("A", "APPLIANCE", "⌂", "icon-orange"),
        ("C", "CIRCUIT BREAKER", "⛨", "icon-red"),
        ("O", "OVERLOAD", "ϟ", "icon-orange"),
        ("E", "CONNECTION", "⌁", "icon-cyan"),
    ]
    with get_connection() as connection:
        latest = connection.execute(
            "SELECT observations FROM diagnoses ORDER BY id DESC LIMIT 1"
        ).fetchone()
    facts: Dict[str, bool] = {}
    if latest:
        facts = {item["symbol"]: item["value"] for item in json.loads(latest["observations"])}
        if models(RULES, facts, [item["symbol"] for item in PROPOSITIONS]):
            facts.update(forward_chain(facts, RULES).derived)
    values = {}
    for symbol in ("P", "M", "F", "W", "B", "L", "S", "A", "C", "O", "E"):
        if symbol not in facts:
            values[symbol] = "Unknown"
        else:
            values[symbol] = _fact_label(symbol, facts[symbol]).split(": ", 1)[1]
    indicators = [
        {"symbol": symbol, "label": label, "icon": icon, "icon_class": icon_class, "value": values[symbol]}
        for symbol, label, icon, icon_class in cards
    ]
    return render_template("index.html", page="dashboard", title="Dashboard",
                           indicators=indicators, has_latest=latest is not None)


@app.get("/diagnosis")
def diagnosis_page():
    return render_template("diagnosis.html", page="diagnosis", title="Fault diagnosis")


@app.get("/knowledge-base")
def knowledge_base_page():
    return render_template("knowledge_base.html", page="knowledge", title="Knowledge base",
                           propositions=PROPOSITIONS)


@app.get("/rules")
def rules_page():
    return render_template("rules.html", page="rules", title="Logical rules", rules=RULES)


@app.get("/reasoning")
def reasoning_page():
    return render_template("reasoning.html", page="reasoning", title="Reasoning lab")


@app.get("/history")
def history_page():
    with get_connection() as connection:
        entries = connection.execute("SELECT * FROM diagnoses ORDER BY id DESC LIMIT 100").fetchall()
    history = [
        {
            "id": item["id"], "created_at": item["created_at"],
            "observations": json.loads(item["observations"]),
            "diagnosis": item["diagnosis"],
            "causes": json.loads(item["possible_causes"]),
            "steps": json.loads(item["explanation"]),
        }
        for item in entries
    ]
    return render_template("history.html", page="history", title="Diagnosis history", history=history)


@app.get("/about")
def about_page():
    return render_template("about.html", page="about", title="About project")


@app.post("/api/diagnose")
def diagnose_api():
    payload = request.get_json(silent=True) or request.form
    observations, labels, errors = _read_observations(payload)
    if errors:
        return jsonify({"error": "Please correct the submitted observations.", "details": errors}), 400
    result = _diagnose(observations, labels)
    result["history_id"] = _save_diagnosis(result)
    return jsonify(result)


@app.post("/api/scenario/<int:scenario_id>")
def scenario_api(scenario_id: int):
    scenarios = {
        1: {"name": "Light failure — fuse observed unhealthy",
            "facts": {"P": True, "M": True, "F": False, "L": False}},
        2: {"name": "Power supply failure", "facts": {"P": False, "L": False}},
        3: {"name": "Bulb failure", "facts": {"P": True, "M": True, "F": True, "W": True, "B": False, "L": False}},
        4: {"name": "Healthy light", "facts": {"P": True, "M": True, "F": True, "W": True, "B": True}},
        5: {"name": "Multiple possible light-failure causes",
            "facts": {"P": True, "M": True, "L": False}},
    }
    scenario = scenarios.get(scenario_id)
    if not scenario:
        return jsonify({"error": "Scenario not found."}), 404
    labels = [_fact_label(symbol, value) for symbol, value in scenario["facts"].items()]
    result = _diagnose(scenario["facts"], labels)
    result["scenario"] = scenario["name"]
    result["history_id"] = _save_diagnosis(result)
    return jsonify(result)


@app.post("/api/entailment")
def entailment_api():
    payload = request.get_json(silent=True) or request.form
    observations, labels, errors = _read_observations(payload)
    if errors:
        return jsonify({"error": "Please correct the submitted observations.", "details": errors}), 400
    source = str(payload.get("query", "")).strip()
    try:
        query = parse_formula(source)
    except FormulaError as error:
        return jsonify({"error": str(error)}), 400
    unknown_symbols = query.symbols() - set(PROPOSITION_BY_SYMBOL)
    if unknown_symbols:
        return jsonify({"error": f"Unknown proposition(s): {', '.join(sorted(unknown_symbols))}"}), 400

    evidence = entailment(query, RULES, observations, [item["symbol"] for item in PROPOSITIONS])
    proof = backward_chain(query, RULES, observations)
    support_models = evidence.pop("support", [])
    refutation_models = evidence.pop("refutation", [])
    explanation = {
        "INCONSISTENT": "The rules and observations have no satisfying models; entailment is undefined for inconsistent evidence.",
        "TRUE": "Every satisfying model of the rules and observations makes this proposition true.",
        "FALSE": "Every satisfying model of the rules and observations makes this proposition false.",
        "UNKNOWN": "Some satisfying models make this proposition true and others make it false. The available evidence does not settle it.",
    }[evidence["status"]]
    return jsonify({
        **evidence,
        "query": source,
        "observations": labels,
        "explanation": explanation,
        "backward_proof": proof,
        "support_models": support_models,
        "refutation_models": refutation_models,
    })


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
