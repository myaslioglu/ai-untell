VENV := .venv
PY := $(VENV)/bin/python
SKILL_HOME := $(HOME)/.claude/skills/ai-untell

.PHONY: setup test lint demo skill skill-check skill-zip install-skill clean

setup:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[all]"

test:
	$(PY) -m pytest tests/ -v

lint:
	$(PY) -m ruff check src tests tools

demo:
	$(PY) examples/demo_clean.py

# Regenerate the stdlib-only engine bundled in skills/ai-untell from src/.
skill:
	$(PY) tools/build_skill.py

skill-check:
	$(PY) tools/build_skill.py --check

# dist/ai-untell-skill.zip: upload to claude.ai (Customize > Skills).
skill-zip:
	$(PY) tools/build_skill.py --zip

# Install the skill for local Claude Code (personal scope).
install-skill: skill
	rm -rf $(SKILL_HOME)
	mkdir -p $(dir $(SKILL_HOME))
	cp -R skills/ai-untell $(SKILL_HOME)
	find $(SKILL_HOME) -name __pycache__ -type d -prune -exec rm -rf {} +

clean:
	rm -rf $(VENV) build dist src/*.egg-info .pytest_cache
