#!/bin/bash
# Mock kMigratorExtract.sh
# Simulates OpenText PPM entity extraction for testing

set -e

# Parse command line arguments
USERNAME=""
PASSWORD=""
URL=""
ACTION=""
ENTITY_ID=""
REFERENCE_CODE=""
FILENAME=""
QUIET=""

while [[ $# -gt 0 ]]; do
  case $1 in
    -username) USERNAME="$2"; shift 2;;
    -password) PASSWORD="$2"; shift 2;;
    -url) URL="$2"; shift 2;;
    -action) ACTION="$2"; shift 2;;
    -entityId) ENTITY_ID="$2"; shift 2;;
    -referenceCode) REFERENCE_CODE="$2"; shift 2;;
    -filename) FILENAME="$2"; shift 2;;
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

if [[ -z "$ENTITY_ID" ]]; then
  echo "Error: Missing required parameter: -entityId" >&2
  exit 1
fi

if [[ -z "$REFERENCE_CODE" ]]; then
  echo "Error: Missing required parameter: -referenceCode" >&2
  echo "Note: -referenceCode is MANDATORY per OpenText PPM kMigratorExtract spec" >&2
  exit 1
fi

# Generate output filename if not provided
if [[ -z "$FILENAME" ]]; then
  TIMESTAMP=$(date +%Y%m%d%H%M%S)
  FILENAME="./bundles/KMIGRATOR_EXTRACT_${ENTITY_ID}_${REFERENCE_CODE}_${TIMESTAMP}.xml"
fi

# Create bundles directory if it doesn't exist
mkdir -p "$(dirname "$FILENAME")"

# Print extraction info (unless quiet mode)
if [[ -z "$QUIET" ]]; then
  echo "=========================================="
  echo "Mock kMigratorExtract"
  echo "=========================================="
  echo "Action: $ACTION"
  echo "Entity ID: $ENTITY_ID"
  echo "Reference Code: $REFERENCE_CODE"
  echo "Source URL: $URL"
  echo "Username: $USERNAME"
  echo ""
fi

# Simulate extraction delay
sleep 1

# Generate mock bundle XML
cat > "$FILENAME" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<EntityBundle>
  <Metadata>
    <EntityId>$ENTITY_ID</EntityId>
    <ReferenceCode>$REFERENCE_CODE</ReferenceCode>
    <ExtractedFrom>$URL</ExtractedFrom>
    <ExtractedAt>$(date -u +%Y-%m-%dT%H:%M:%SZ)</ExtractedAt>
    <ExtractedBy>$USERNAME</ExtractedBy>
  </Metadata>
  <Entities>
    <Entity>
      <Code>$REFERENCE_CODE</Code>
      <Name>Mock Entity $REFERENCE_CODE</Name>
      <Type>EntityType_$ENTITY_ID</Type>
      <Description>This is a mock entity for testing purposes</Description>
    </Entity>
  </Entities>
</EntityBundle>
EOF

if [[ -z "$QUIET" ]]; then
  echo "Extraction successful!"
  echo "Bundle saved to: $FILENAME"
  echo "=========================================="
fi

exit 0
