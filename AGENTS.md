# Agent Instructions: restic-subset-calculator

## Project Requirements
- **Language:** Python 3.12+
- **Dependency Management:** PDM
- **Formatting & Linting:** Ruff
- **Testing:** Pytest, pytest-mock, pytest-cov
- **Coverage:** **100% test coverage is required** for `restic_subset_calculator.py`.

## Subsetting Algorithm
The tool must strictly follow restic's `n/t` subsetting logic:
- Extracts the first byte of the pack ID (first two hex characters).
- Subset `n` (1-based) is assigned if `first_byte % t == n - 1`.

## Pre-Commit Checklist
Before submitting any changes, you **must** run the following commands and ensure they pass:

### 1. Formatting and Linting
```bash
pdm run ruff format .
pdm run ruff check . --fix
```

### 2. Testing and Coverage
```bash
PYTHONPATH=. pdm run pytest --cov --cov-report=term-missing
```
**Ensure the output shows:**
`Required test coverage of 100.0% reached.`

## Restic Command Handling
- All restic commands must be executed via the `run_restic` helper.
- JSON output from restic must be parsed using `parse_json_output` to handle NDJSON and raw ID lists.
- All download sizes must be tracked and reported when `--debug` is active.
