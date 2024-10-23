#!/usr/bin/env bash

FAILED=0
FAILURE_REASONS=()

export TAG_SUFFIX="${BUILD_NUMBER:-$(date +%s)}"

add_failure () {
  FAILED=1
  FAILURE_REASONS+=("Failed $1. Investigate locally with: $2")
}

make build-image || add_failure "image build" "make build-image"
make check-format || add_failure "formatting" "make format"
make mypy || add_failure "type checking" "make mypy"
make test || add_failure "unit tests" "make test"
ci/run.sh || add_failure "integration tests" "ci/run.sh"

for failure_reason in "${FAILURE_REASONS[@]}"
do
  echo "$failure_reason" >&2
done

exit $FAILED
