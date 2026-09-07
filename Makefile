.PHONY: install dev run lint format check_servers check_bindings check_smtp remake_db fresh_dev docker_build docker_up docker_down docker_logs

PIPENV := pipenv run
APP := app.main:app
DB := vibe_mail.db

install:
	pipenv install

dev:
	$(PIPENV) uvicorn $(APP) --reload

run:
	$(PIPENV) uvicorn $(APP)

lint:
	$(PIPENV) ruff check

format:
	$(PIPENV) ruff format

check_servers:
	$(PIPENV) python check_servers.py

check_bindings:
	$(PIPENV) python check_servers.py --bindings

check_smtp:
	$(PIPENV) python check_smtp.py

docker_build:
	docker compose build

# data/ создаём заранее: docker создал бы его от root, и потом не удалить без sudo.
docker_up: | data
	docker compose up -d
	@echo "Интерфейс: http://localhost:8000"

data:
	mkdir -p data

docker_down:
	docker compose down

docker_logs:
	docker compose logs -f

remake_db:
	rm -f $(DB)
	$(PIPENV) python seed_campaigns.py

fresh_dev:
	$(MAKE) remake_db
	$(MAKE) dev
