#!/bin/bash

./scripts/install-pip-tools.sh

PIP_EXISTS_ACTION=w

set -euxo pipefail
PYTHONPATH="" pip-sync dev-requirements.txt
