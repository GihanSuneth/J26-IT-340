# Makefile - Developer shortcuts: make setup | lint | test | up | down.
# Owner: develop (shared - all four members review)

.PHONY: setup lint test up down
setup:
	bash scripts/bootstrap.sh
lint:
	ruff check backend shared tests
test:
	pytest backend tests/contract
up:
	docker compose up --build
down:
	docker compose down
