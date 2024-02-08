#!/usr/bin/env bash

set -euo pipefail
cd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

rm -rf dist

export TWINE_NON_INTERACTIVE=1
export TWINE_USERNAME='__token__'
export TWINE_PASSWORD=$AI2_NORA_PYPI_TOKEN

pip install --upgrade pip setuptools wheel build twine
python -m build
twine upload dist/*
