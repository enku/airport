PYTHON = python3.4
NAME = airport

export DJANGO_DEBUG


requirements: requirements.txt
	$(PYTHON) -m pip -q install -r $<


test:
	tox

docker:
	docker-compose -p $(NAME) -f tools/docker/docker-compose.yml build
	docker-compose -p $(NAME) -f tools/docker/docker-compose.yml up

.PHONY: requirements test
