.PHONY: help install dev test lint typecheck format clean run

help:
	@printf '%s\n' \
		'install   - install package with dev extras' \
		'dev       - run development server' \
		'test      - run pytest suite' \
		'lint      - run ruff' \
		'typecheck - run mypy' \
		'format    - run ruff --fix' \
		'run       - run production entrypoint' \
		'clean     - remove caches and build artifacts'

install:
	pip install -e '.[dev]'

dev:
	./scripts/dev.sh

test:
	./scripts/test.sh

lint:
	./scripts/lint.sh

typecheck:
	mypy app

format:
	ruff check --fix app tests

run:
	python -m app.main

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
