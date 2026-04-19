# restic-tools

A collection of restic helper tools.

## Tools

### restic-subset-calculator

Calculate restic check --read-data-subset stats.

## Development

This project uses PDM for dependency management.

### Setup

```bash
pdm install
```

### Running Tests

```bash
pdm run pytest
```

### Formatting and Linting

```bash
pdm run ruff format .
pdm run ruff check . --fix
```
