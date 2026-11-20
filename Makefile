.PHONY: setup bootstrap start stop reset test verify lint format-check build smoke clean docs

setup:
	cp -n .env.example .env || true

bootstrap:
	./scripts/bootstrap.sh

start:
	docker compose up --detach --build

stop:
	./scripts/stop.sh

reset:
	./scripts/reset.sh

test:
	uv run pytest

verify:
	uv run pytest --cov --cov-report=term-missing

lint:
	uv run ruff format --check src tests
	uv run ruff check src tests
	uv run mypy src

format-check: lint

build:
	docker build --tag $${EXCHANGE_IMAGE:-microsserv52-exchange:local} .

smoke:
	./scripts/smoke.sh

clean:
	uv run pytest --cov --cov-report=term-missing --no-cov-on-fail >/dev/null 2>&1 || true
	rm -rf site .coverage coverage.xml htmlcov

docs:
	uvx --from zensical==0.0.74 zensical build --clean
