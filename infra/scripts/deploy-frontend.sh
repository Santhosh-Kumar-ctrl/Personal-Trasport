#!/usr/bin/env bash
# Build the Flutter web app and sync it to the frontend bucket.
# Usage: infra/scripts/deploy-frontend.sh <bucket> <api-base-url>
set -euo pipefail
BUCKET="${1:?usage: deploy-frontend.sh <bucket> <api-base-url>}"
API_URL="${2:?usage: deploy-frontend.sh <bucket> <api-base-url>}"
cd "$(dirname "$0")/../../frontend"
flutter build web --release --dart-define=API_BASE="$API_URL"
aws s3 sync build/web "s3://${BUCKET}" --delete
echo "Deployed to s3://${BUCKET}"
