#!/bin/bash
# Mock kMigratorImport.sh
# Simulates OpenText PPM entity import for testing

set -e

# Parse command line arguments
USERNAME=""
PASSWORD=""
URL=""
ACTION=""
FILENAME=""
I18N=""
REFDATA=""
FLAGS=""
QUIET=""

while [[ $# -gt 0 ]]; do
  case $1 in
    -username) USERNAME="$2"; shift 2;;
    -password) PASSWORD="$2"; shift 2;;
    -url) URL="$2"; shift 2;;
    -action) ACTION="$2"; shift 2;;
    -filename) FILENAME="$2"; shift 2;;
    -i18n) I18N="$2"; shift 2;;
    -refdata) REFDATA="$2"; shift 2;;
    -flags) FLAGS="$2"; shift 2;;
    -quiet) QUIET="true"; shift;;
    *) shift;;
  esac
done

# Validate required parameters
if [[ -z "$USERNAME" ]]; then
  echo "Error: Missing required parameter: -username" >&2
  exit 1
fi

if [[ -z "$ACTION" ]]; then
  echo "Error: Missing required parameter: -action" >&2
  exit 1
fi

if [[ -z "$FILENAME" ]]; then
  echo "Error: Missing required parameter: -filename" >&2
  exit 1
fi

if [[ -z "$FLAGS" ]]; then
  echo "Error: Missing required parameter: -flags" >&2
  exit 1
fi

# Check bundle file exists
if [[ ! -f "$FILENAME" ]]; then
  echo "Error: Bundle file not found: $FILENAME" >&2
  exit 1
fi

# Validate flags (must be exactly 25 characters, only Y/N)
if [[ ${#FLAGS} -ne 25 ]]; then
  echo "Error: Flags must be exactly 25 characters, got ${#FLAGS}" >&2
  exit 1
fi

if [[ ! "$FLAGS" =~ ^[YN]+$ ]]; then
  echo "Error: Flags must contain only Y or N characters" >&2
  exit 1
fi

# Parse bundle XML to extract entity information (compatible with macOS)
ENTITY_ID=$(grep '<EntityId>' "$FILENAME" 2>/dev/null | sed 's/.*<EntityId>\(.*\)<\/EntityId>.*/\1/' || echo "UNKNOWN")
REF_CODE=$(grep '<ReferenceCode>' "$FILENAME" 2>/dev/null | sed 's/.*<ReferenceCode>\(.*\)<\/ReferenceCode>.*/\1/' || echo "UNKNOWN")

# Print import info (unless quiet mode)
if [[ -z "$QUIET" ]]; then
  echo "=========================================="
  echo "Mock kMigratorImport"
  echo "=========================================="
  echo "Action: $ACTION"
  echo "Bundle File: $FILENAME"
  echo "Target URL: $URL"
  echo "Username: $USERNAME"
  echo "Flags: $FLAGS"
  echo "i18n: ${I18N:-none}"
  echo "refdata: ${REFDATA:-nochange}"
  echo ""
  echo "Parsing bundle..."
  echo "  Entity ID: $ENTITY_ID"
  echo "  Reference Code: $REF_CODE"
  echo ""
fi

# Simulate import delay
sleep 2

if [[ -z "$QUIET" ]]; then
  echo "Validating entity..."
  echo "Checking dependencies..."
  echo "Applying changes..."
  echo ""
  echo "Import successful!"
  echo "1 entity imported, 0 errors"
  echo "=========================================="
fi

exit 0
