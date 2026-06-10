#!/usr/bin/env bash
# Upload a control document to one or all orgs via POST /api/v1/control-documents/upload
#
# Usage:
#   ./upload_to_orgs.sh                              # all orgs, sample PDF
#   ./upload_to_orgs.sh /path/to/doc.pdf             # all orgs, your file
#   ./upload_to_orgs.sh /path/to/doc.pdf ORG_UUID   # single org only
#
# Environment:
#   API_BASE=http://localhost:8000/api/v1
#   ADMIN_EMAIL=admin@catalytics.local
#   ADMIN_PASSWORD=AdminPWD123!

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@catalytics.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-AdminPWD123!}"
FILE="${1:-$ROOT/fixtures/sample_control.pdf}"
ORG_ID="${2:-}"

ensure_sample_pdf() {
  local dest="$ROOT/fixtures/sample_control.pdf"
  [[ -f "$dest" ]] && return
  mkdir -p "$ROOT/fixtures"
  python3 - "$dest" << 'PY'
import sys
from pathlib import Path
pdf = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R>>endobj
4 0 obj<</Length 55>>stream
BT /F1 24 Tf 100 700 Td (ISO Robot sample control) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000052 00000 n 
0000000101 00000 n 
0000000179 00000 n 
trailer<</Size 5/Root 1 0 R>>
startxref
285
%%EOF"""
Path(sys.argv[1]).write_bytes(pdf)
print(f"Created {sys.argv[1]}")
PY
}

if [[ ! -f "$FILE" ]]; then
  ensure_sample_pdf
  FILE="$ROOT/fixtures/sample_control.pdf"
fi

echo "==> Login ($ADMIN_EMAIL)"
LOGIN=$(curl -s -X POST "$API_BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")

TOKEN=$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('data',{}).get('access_token',''))" "$LOGIN")
if [[ -z "$TOKEN" ]]; then
  echo "Login failed: $LOGIN"
  exit 1
fi
echo "    token ok"

upload_one() {
  local org_id="$1"
  local label="$2"
  echo ""
  echo "==> Upload → $label ($org_id)"
  curl -s -X POST "$API_BASE/control-documents/upload" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/json" \
    -F "client_org_id=$org_id" \
    -F "document_type=policy" \
    -F "document_category=ISO27001" \
    -F "file=@$FILE" | python3 -m json.tool
}

if [[ -n "$ORG_ID" ]]; then
  upload_one "$ORG_ID" "selected org"
  echo ""
  echo "List documents:"
  curl -s "$API_BASE/control-documents/$ORG_ID" \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
  exit 0
fi

echo "==> Fetch all organisations"
ORGS_JSON=$(curl -s "$API_BASE/orgs" -H "Authorization: Bearer $TOKEN")
echo "$ORGS_JSON" | python3 -m json.tool

while IFS=$'\t' read -r oid oname; do
  [[ -z "$oid" ]] && continue
  upload_one "$oid" "$oname"
done < <(python3 -c "
import json, sys
for o in json.loads(sys.argv[1])['data']['organisations']:
    print(o['id'] + '\t' + o['name'])
" "$ORGS_JSON")

echo ""
echo "Done. Example list (platform org from admin login):"
echo "  curl -s \"$API_BASE/control-documents/686f6c71-77f3-45fc-812b-d6a6c09e76b9\" \\"
echo "    -H \"Authorization: Bearer \$TOKEN\" | python3 -m json.tool"
