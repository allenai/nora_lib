#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/../"

cleanup() {
  # Clear the trap, so we don't repeat infinitely
  trap '' 0

  set +e
  echo 'Attempting to cleanup...'
  docker compose -f ci/compose.yaml down
  echo 'Cleaned house.'
}

# This trap will run if this script exits for any reason, error or not.
trap cleanup 0

make ecr-login
docker compose -f ci/compose.yaml up -d

# Run tests
make test-it
