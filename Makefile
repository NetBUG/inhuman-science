.PHONY: deploy stop restart logs backup update status

deploy:
	docker compose up -d --build

stop:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=100

backup:
	docker compose exec inhuman-science python main.py backup

status:
	docker compose ps

update:
	git pull origin master
	docker compose up -d --build
