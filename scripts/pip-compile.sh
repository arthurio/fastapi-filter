#!/bin/bash

./scripts/install-pip-tools.sh

set -euxo pipefail
PYTHONPATH="" pip-compile requirements.in --output-file requirements.txt
PYTHONPATH="" pip-compile dev-requirements.in --output-file dev-requirements.txt
