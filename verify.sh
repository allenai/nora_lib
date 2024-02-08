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
make pytest || add_failure "TIMO unit tests" "make pytest"
make it || add_failure "integration tests" "make it"

for failure_reason in "${FAILURE_REASONS[@]}"
do
  echo "$failure_reason" >&2
done

exit $FAILED
