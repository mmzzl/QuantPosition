.PHONY: check test e2e install deploy down lint

check:
	python -m compileall apps/api

install:
	pip install -r apps/api/requirements.txt

test:
	python -m pytest apps/api/tests -v --tb=short

e2e:
	python -m pytest apps/api/e2e -v --tb=short

deploy:
	docker compose up -d --build

down:
	docker compose down

lint:
	python -m flake8 apps/api --max-line-length=120 --exclude=__pycache__
