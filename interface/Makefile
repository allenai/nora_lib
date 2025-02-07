IMAGE_TAG = nora-lib$(OPTIONAL_TAG)
DOCKER_RUN = docker run --rm $(IMAGE_TAG)

copy-version:
	cp ../version.txt .

copy-src:
	rsync -a --delete --exclude "impl/*" ../impl/src/ src/

build-image: copy-version copy-src
	docker build --build-arg NORA_LIB_VERSION=`cat version.txt` --quiet . -t $(IMAGE_TAG)

mypy: build-image
	$(DOCKER_RUN) /bin/bash -c 'mypy src'

verify: mypy
