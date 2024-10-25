ifdef TAG_SUFFIX
	OPTIONAL_TAG = -$(TAG_SUFFIX)
endif

IMAGE_TAG = nora-lib$(OPTIONAL_TAG)
DOCKER_NETWORK = nora-lib-network

DOCKER_RUN = docker run --rm --env-file docker.env $(IMAGE_TAG)
DOCKER_RUN_WITH_NETWORK = docker run --rm --env-file docker.env --network=$(DOCKER_NETWORK) $(IMAGE_TAG)

build-image:
	docker build . -t $(IMAGE_TAG) --platform linux/amd64

check-format:
	$(DOCKER_RUN) black --check --diff nora_lib

mypy: build-image
	$(DOCKER_RUN) /bin/bash -c 'mypy nora_lib tests'

test: build-image
	$(DOCKER_RUN) python -m pytest tests/unit

ecr-login:
	aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 896129387501.dkr.ecr.us-west-2.amazonaws.com
	aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws

# Don't run directly. Run `ci/run.sh` instead.
test-it: build-image
	$(DOCKER_RUN_WITH_NETWORK) python -m pytest tests/integration

format:
	docker run --rm \
		-v $(shell pwd):/work \
		$(IMAGE_TAG) \
		black nora_lib tests
