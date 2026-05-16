.PHONY: setup dev test lint format seed eval benchmark docker-up docker-down

setup:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

dev:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	python -m pytest

lint:
	python -m ruff check .
	python -m mypy app tests scripts

format:
	python -m ruff format .
	python -m ruff check . --fix

seed:
	python scripts/seed_demo_data.py

eval:
	python scripts/run_eval.py --dataset evals/datasets/regulatory_qa.jsonl

benchmark:
	python scripts/benchmark.py --requests 100 --concurrency 10

docker-up:
	docker compose up -d

docker-down:
	docker compose down
