IMAGE_TAG = nora-lib-impl$(OPTIONAL_TAG)
DOCKER_NETWORK = nora-lib-network

DOCKER_RUN = docker run --rm --env-file docker.env $(IMAGE_TAG)
DOCKER_RUN_WITH_NETWORK = docker run --rm --env-file docker.env --network=$(DOCKER_NETWORK) $(IMAGE_TAG)
DOCKER_COMPOSE = docker compose -f ci/compose.yaml

copy-version:
	cp ../version.txt .

build-image: copy-version
	docker build --quiet . -t $(IMAGE_TAG)

check-format: build-image
	$(DOCKER_RUN) black --check --diff src

format: build-image
	docker run -v `pwd`:/work --rm $(IMAGE_TAG) black src tests

mypy: build-image
	$(DOCKER_RUN) /bin/bash -c 'mypy src tests'

test: build-image
	$(DOCKER_RUN) python -m pytest tests/unit

ecr-login:
	aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 896129387501.dkr.ecr.us-west-2.amazonaws.com
	aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws

test-it-setup: ecr-login
	$(DOCKER_COMPOSE) up -d --wait

test-it-run:
	$(DOCKER_RUN_WITH_NETWORK) python -m pytest tests/integration

test-it-teardown:
	$(DOCKER_COMPOSE) down

test-it: test-it-setup test-it-run test-it-teardown

verify: check-format mypy test
# Run with --keep-going to guarantee tear-down
	make --keep-going test-it

