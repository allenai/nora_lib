ifdef TAG_SUFFIX
	OPTIONAL_TAG = -$(TAG_SUFFIX)
endif

IMAGE_TAG = nora-lib$(OPTIONAL_TAG)

build-image:
	docker build . -t $(IMAGE_TAG) --platform linux/amd64

check-format:
	docker run --rm  $(IMAGE_TAG) black --check --diff nora_lib

mypy: build-image
	docker run --rm $(IMAGE_TAG) /bin/bash -c 'mypy nora_lib tests'

pytest:
	docker run --rm --env-file docker.env $(IMAGE_TAG) pytest

format:
	docker run --rm -it \
		-v $(shell pwd):/work \
		$(IMAGE_TAG) \
		black nora_lib tests

