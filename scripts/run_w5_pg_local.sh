#!/usr/bin/env bash
# Explicit opt-in, zero-GitHub-Actions local PostgreSQL parity experiment.
# IMPORTANT: This creates a throwaway Docker container, never touches an existing DB.
set -Eeuo pipefail

if [[ $# -ne 0 ]]; then
  printf 'Usage: OPENWORLD_PG_LOCAL_CONFIRM=YES_EPHEMERAL_CONTAINER bash scripts/run_w5_pg_local.sh\n' >&2
  exit 2
fi
if [[ "${OPENWORLD_PG_LOCAL_CONFIRM:-}" != 'YES_EPHEMERAL_CONTAINER' ]]; then
  printf 'REFUSED: set OPENWORLD_PG_LOCAL_CONFIRM=YES_EPHEMERAL_CONTAINER after reviewing the local Docker experiment.\n' >&2
  exit 2
fi

for binary in docker python3 git; do
  if ! command -v "$binary" >/dev/null 2>&1; then
    printf 'REFUSED: missing required command: %s\n' "$binary" >&2
    exit 2
  fi
done

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$repo_root/benchmarks/w5_storage_parity.py" || ! -f "$repo_root/scripts/verify_w5_pg_report.py" ]]; then
  printf 'REFUSED: expected OpenWorld source files not found.\n' >&2
  exit 2
fi
if ! python3 -c 'import sys,psycopg; assert sys.version_info >= (3,11)' >/dev/null 2>&1; then
  printf 'REFUSED: Python 3.11+ with optional psycopg 3 is required. No packages were installed.\n' >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  printf 'REFUSED: Docker engine is not available.\n' >&2
  exit 2
fi
if ! docker image inspect postgres:16 >/dev/null 2>&1; then
  printf 'REFUSED: postgres:16 is not downloaded. Review the image and run docker pull postgres:16 yourself first.\n' >&2
  exit 2
fi

umask 077
report_dir="$(mktemp -d "${TMPDIR:-/tmp}/openworld-pg-parity.XXXXXXXX")"
container_id=''
cleanup() {
  if [[ -n "$container_id" ]]; then
    if ! docker rm -f "$container_id" >/dev/null 2>&1; then
      printf 'WARNING: unable to remove ephemeral Docker container %s. Remove it manually.\n' "$container_id" >&2
    fi
  fi
  rm -f -- "$report_dir/postgres.env"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf 'POSTGRES_USER=openworld_research\nPOSTGRES_PASSWORD=%s\nPOSTGRES_DB=openworld_ephemeral_local\n' "$password" > "$report_dir/postgres.env"
name="openworld-pg-parity-$$-$RANDOM"
container_id="$(docker run --rm --detach --pull=never --name "$name" --publish '127.0.0.1::5432' --env-file "$report_dir/postgres.env" postgres:16)"
rm -f -- "$report_dir/postgres.env"

# An IPv4 localhost-only ephemeral host port prevents accidental LAN exposure.
published="$(docker port "$container_id" 5432/tcp)"
if [[ ! "$published" =~ ^127\.0\.0\.1:([0-9]{1,5})$ ]]; then
  printf 'REFUSED: unexpected PostgreSQL port binding.\n' >&2
  exit 2
fi
port="${BASH_REMATCH[1]}"
if (( 10#$port < 1 || 10#$port > 65535 )); then
  printf 'REFUSED: invalid local port.\n' >&2
  exit 2
fi

ready=''
for ((i=0; i<40; i++)); do
  if docker exec "$container_id" pg_isready -U openworld_research -d openworld_ephemeral_local >/dev/null 2>&1; then
    ready=yes
    break
  fi
  sleep 0.5
done
if [[ "$ready" != yes ]]; then
  printf 'REFUSED: temporary PostgreSQL service did not become ready.\n' >&2
  exit 2
fi

report="$report_dir/w5-parity-result.json"
sha="$(git -C "$repo_root" rev-parse HEAD)"
image_id="$(docker image inspect --format '{{.Id}}' postgres:16)"
(
  cd "$repo_root"
  OPENWORLD_PG_TEST_ISOLATED=YES_EPHEMERAL_DB \
  OPENWORLD_PG_TEST_DSN="postgresql://openworld_research:${password}@127.0.0.1:${port}/openworld_ephemeral_local" \
    python3 benchmarks/w5_storage_parity.py --with-postgres > "$report"
  python3 scripts/verify_w5_pg_report.py "$report"
)
python3 - "$report" "$report_dir/run-metadata.json" "$sha" "$image_id" <<'PY'
import hashlib
import json
import sys
from pathlib import Path
report, metadata, commit_sha, image_id = sys.argv[1:]
blob = Path(report).read_bytes()
Path(metadata).write_text(json.dumps({
    'source_commit': commit_sha,
    'docker_image_id': image_id,
    'report_sha256': hashlib.sha256(blob).hexdigest(),
    'status': 'LOCAL_SYNTHETIC_PARITY_NOT_ATTESTED',
}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
PY
printf 'LOCAL SYNTHETIC PARITY VALIDATED (not authenticated production evidence).\n'
printf 'Report files: %s\n' "$report_dir"
printf 'The temporary PostgreSQL container is being removed.\n'