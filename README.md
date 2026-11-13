# CircuitSense — Smart Home Fault Diagnosis Using Propositional Logic

CircuitSense is an educational Flask application that demonstrates propositional-logic reasoning over simplified smart-home electrical conditions. It accepts known observations, applies an explicit rule base, checks for contradictions, lists possible explanations without treating them as proven facts, and shows a step-by-step reasoning trace.

> **Safety:** This application is an educational AI fault diagnosis simulator. It does not perform real electrical testing. Electrical faults should be inspected by a qualified electrician. Do not use the simulator as instructions to touch, test, or repair electrical equipment.

## Features

- Responsive dark dashboard and navigation for dashboard, diagnosis, knowledge base, rules, reasoning lab, history, and project information.
- A separate Python propositional-logic engine supporting `¬` (NOT), `∧` (AND), `∨` (OR), `→` (IF–THEN), modus ponens, forward chaining, backward chaining, model checking, entailment, and consistency checking.
- Unknown conditions remain unknown. They are never silently converted to false.
- Diagnosis results distinguish observations, proven conclusions, possible explanations, unknown conditions, and contradictory evidence.
- Five interactive demonstration scenarios and a truth-table/model-checking entailment form.
- SQLite persistence for recent diagnosis records and their reasoning traces.

## Requirements

- Python 3.9 or later
- pip
- VS Code (recommended)

## Run on Windows in VS Code

Open the project folder in VS Code, then open **Terminal → New Terminal** and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, use the Python executable in the virtual environment directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open the local address printed by Flask (normally `http://127.0.0.1:5000`). Stop the development server with **Ctrl+C**. For a production deployment, use a production WSGI server and disable debug mode.

To run the test suite:

```powershell
python -m unittest discover -s tests -v
```

## How reasoning works

1. The form converts selected states and symptoms to signed propositions (for example, `P = false` is the fact `¬P`). Unselected states are omitted.
2. The engine applies rules whose premises are known true, using three-valued partial evaluation; this is forward chaining and modus ponens.
3. For an observed failed output, the app lists relevant unobserved inputs only as possible causes when the observations plus that candidate remain consistent with the knowledge base. A false output does not, by itself, prove which component is faulty.
4. It enumerates truth assignments satisfying both the rule base and observations to detect inconsistency and to answer entailment queries. A query is `TRUE` if all satisfying models make it true, `FALSE` if all make it false, `UNKNOWN` if models disagree, and `INCONSISTENT` when there are no satisfying models.
5. Literal goal queries can additionally be traced with backward chaining. Complex formulas are handled by model checking.

### Example

If `P` and `M` are observed true, and `L` is observed false, the system does **not** conclude that `F` is false. It lists a fuse issue, wiring fault, and bulb fault as possible explanations (subject to consistency) and states that more observations are needed.

## Knowledge base

| Symbol | Proposition |
|---|---|
| `P` | Power supply available |
| `M` | Main switch ON |
| `F` | Fuse healthy |
| `W` | Wiring healthy |
| `B` | Bulb healthy |
| `L` | Light functioning |
| `S` | Socket functioning |
| `A` | Appliance functioning |
| `C` | Circuit breaker ON |
| `O` | Overload detected |
| `E` | Electrical connection healthy |

Rules are declared in `knowledge_base.py` and displayed directly from the same data in the application. The model is intentionally simplified and does not represent every protection device or electrical installation behavior.

## Project structure

```text
app.py                  Flask routes, diagnosis API, and SQLite history
logic_engine.py         Formula parser, chaining, model checking, entailment
knowledge_base.py       Propositions and symbolic inference rules
requirements.txt        Python dependencies
templates/              Dashboard and application pages
static/css/style.css    Responsive dark dashboard styles
static/js/script.js     Form submission and result rendering
tests/                  Logic-engine and Flask API tests
database.db             Created automatically when the app first starts
```

The SQLite database is created on first launch in the project directory by default. Set `SMART_HOME_DB` to choose another database file. The Flask development server can optionally be run with debug mode by setting `FLASK_DEBUG=1`; leave it disabled for normal use.
