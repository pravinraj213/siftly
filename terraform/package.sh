#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
rm -f "$project_dir/terraform/siftly-lambda.zip"
(cd "$project_dir/backend" && zip -q "$project_dir/terraform/siftly-lambda.zip" app.py index.html)
