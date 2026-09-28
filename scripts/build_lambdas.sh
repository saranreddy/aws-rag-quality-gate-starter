#!/bin/bash
# Build Lambda deployment packages with dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/../infra"
SRC_DIR="$SCRIPT_DIR/../src"
BUILD_DIR="$INFRA_DIR/build"

echo "Building Lambda deployment packages..."

# Clean previous builds
rm -rf "$BUILD_DIR"

# Build db_init Lambda
echo "Building db_init Lambda..."
mkdir -p "$BUILD_DIR/db_init"
cp "$INFRA_DIR/db_init.py" "$BUILD_DIR/db_init/"
pip install \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --only-binary=:all: \
  --target "$BUILD_DIR/db_init" \
  psycopg2-binary pgvector

# Build ingest Lambda
echo "Building ingest Lambda..."
mkdir -p "$BUILD_DIR/ingest"
cp -r "$SRC_DIR/rag" "$SRC_DIR/lambda_handlers" "$BUILD_DIR/ingest/"
pip install \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --only-binary=:all: \
  --target "$BUILD_DIR/ingest" \
  psycopg2-binary pgvector pypdf reportlab PyYAML

# Build query Lambda
echo "Building query Lambda..."
mkdir -p "$BUILD_DIR/query"
cp -r "$SRC_DIR/rag" "$SRC_DIR/lambda_handlers" "$BUILD_DIR/query/"
pip install \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --only-binary=:all: \
  --target "$BUILD_DIR/query" \
  psycopg2-binary pgvector PyYAML

echo "Lambda build complete!"
echo "Deployment packages in: $BUILD_DIR"
