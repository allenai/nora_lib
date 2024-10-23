ifdef TAG_SUFFIX
	OPTIONAL_TAG = -$(TAG_SUFFIX)
endif

IMAGE_TAG = nora-lib$(OPTIONAL_TAG)
DOCKER_NETWORK = nora-lib-network

DOCKER_RUN = docker run --rm --env-file docker.env --network=$(DOCKER_NETWORK) $(IMAGE_TAG)

build-image:
	docker build . -t $(IMAGE_TAG) --platform linux/amd64

check-format:
	$(DOCKER_RUN) black --check --diff nora_lib

mypy: build-image
	$(DOCKER_RUN) /bin/bash -c 'mypy nora_lib tests'

test: build-image
	$(DOCKER_RUN) python -m pytest tests/unit

test-it: build-image
	$(DOCKER_RUN) python -m pytest tests/integration

format:
	docker run --rm \
		-v $(shell pwd):/work \
		$(IMAGE_TAG) \
		black nora_lib tests
