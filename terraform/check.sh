#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
python3 -m unittest discover -s tests -v
terraform fmt -check -recursive terraform
./terraform/package.sh
terraform -chdir=terraform validate
