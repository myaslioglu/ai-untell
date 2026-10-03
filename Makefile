VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: setup test lint demo clean

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[all]"

test:
	$(PY) -m pytest tests/ -v

lint:
	$(VENV)/bin/ruff check src tests

demo:
	$(PY) examples/demo_clean.py

clean:
	rm -rf $(VENV) build dist src/*.egg-info .pytest_cache
