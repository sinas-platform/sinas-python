#!/bin/bash
# Quick upload script for SINAS SDK to PyPI
# Usage: ./UPLOAD_TO_PYPI.sh [test|prod]

set -e

echo "======================================"
echo "SINAS SDK PyPI Upload"
echo "======================================"
echo ""

# Check if twine is installed
if ! command -v twine &> /dev/null; then
    echo "Error: twine is not installed"
    echo "Install it with: pip install twine"
    exit 1
fi

# Check if dist files exist
if [ ! -f "dist/sinas-0.1.0-py3-none-any.whl" ]; then
    echo "Error: Package not built. Run 'python3 -m build' first"
    exit 1
fi

# Validate packages
echo "Validating packages..."
twine check dist/*
if [ $? -ne 0 ]; then
    echo "Error: Package validation failed"
    exit 1
fi

# Determine upload target
TARGET=${1:-test}

if [ "$TARGET" == "test" ]; then
    echo ""
    echo "Uploading to TEST PyPI..."
    echo "You will need your Test PyPI API token"
    echo ""
    twine upload --repository testpypi dist/*
    echo ""
    echo "✅ Uploaded to Test PyPI!"
    echo "Test installation with:"
    echo "pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ sinas"
elif [ "$TARGET" == "prod" ]; then
    echo ""
    echo "⚠️  WARNING: You are about to upload to PRODUCTION PyPI"
    echo "This action CANNOT be undone!"
    echo ""
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Upload cancelled"
        exit 0
    fi
    echo ""
    echo "Uploading to PRODUCTION PyPI..."
    echo "You will need your PyPI API token"
    echo ""
    twine upload dist/*
    echo ""
    echo "✅ Uploaded to PyPI!"
    echo "Install with: pip install sinas"
else
    echo "Error: Invalid target. Use 'test' or 'prod'"
    exit 1
fi
