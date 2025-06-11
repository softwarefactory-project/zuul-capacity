.PHONY: ci
ci:
	@uv run ruff check --fix
	@uv run ruff format
