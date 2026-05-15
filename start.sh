#!/usr/bin/env bash
set -euo pipefail

app="capstone"
docker build -t "${app}" .
docker run \
    -it \
    --rm \
    -p 3000:80 \
    -v "$PWD/data:/app/data" \
    -v "$PWD/models:/app/models" \
    -v "$PWD/logs:/app/logs" \
    --name "${app}" \
    "${app}"
