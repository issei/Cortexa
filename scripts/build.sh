#!/bin/bash
set -e

ENVIRONMENTS=("dev" "staging" "prod")
FUNCTIONS=("ingest_function" "query_function" "openai_embedding_proxy")

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --environment)
      DEPLOY_ENV="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Validate environment
if [[ ! " ${ENVIRONMENTS[@]} " =~ " ${DEPLOY_ENV} " ]]; then
  echo "Invalid environment. Must be one of: ${ENVIRONMENTS[*]}"
  exit 1
fi

# Create build directory
BUILD_DIR="build/${DEPLOY_ENV}"
mkdir -p "$BUILD_DIR"

# Build each function
for func in "${FUNCTIONS[@]}"; do
  echo "Building $func for $DEPLOY_ENV environment..."

  # Create temporary directory
  TEMP_DIR=$(mktemp -d)

  # Copy function files
  cp "src/${func}/main.py" "$TEMP_DIR/"
  cp "src/${func}/requirements.txt" "$TEMP_DIR/" 2>/dev/null || true

  # Install dependencies if any
  if [ -f "$TEMP_DIR/requirements.txt" ]; then
    pip install -r "$TEMP_DIR/requirements.txt" -t "$TEMP_DIR/"
  fi

  # Create zip package
  (cd "$TEMP_DIR" && zip -r "${BUILD_DIR}/${func}.zip" .)

  # Cleanup
  rm -rf "$TEMP_DIR"
done

echo "Build completed successfully for $DEPLOY_ENV environment"
