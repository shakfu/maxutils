
.PHONEY: test wheel check clean

all: test

test:
	pytest

wheel:
	python3 -m build


check:
	@echo "running mypy checks"
	@mypy maxutils

	@echo "running ruff checks"
	@ruff maxutils

clean:
	@rm -rf dist .pytest_cache maxutils.egg-info .mypy_cache .ruff_cache
	@find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete
