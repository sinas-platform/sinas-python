# Publishing SINAS SDK to PyPI

This guide explains how to publish the SINAS SDK to PyPI.

## Prerequisites

1. **PyPI Account**: You need an account on [PyPI](https://pypi.org/account/register/)
2. **API Token**: Create an API token at https://pypi.org/manage/account/token/
3. **Build Tools**: Ensure you have the latest build tools installed:
   ```bash
   pip install --upgrade build twine
   ```

## Pre-Publication Checklist

- [x] All tests pass
- [x] Version number updated in `pyproject.toml`
- [x] `CHANGELOG.md` updated with release notes
- [x] README.md is complete and accurate
- [x] All APIs match OpenAPI specification
- [x] Package builds successfully
- [x] Installation test passes
- [x] FastAPI extras work correctly

## Build the Package

From the `sinas-sdk` directory:

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build both wheel and source distribution
python3 -m build
```

This creates:
- `dist/sinas-0.1.0-py3-none-any.whl` (wheel)
- `dist/sinas-0.1.0.tar.gz` (source distribution)

## Verify the Package

```bash
# Check package validity
twine check dist/*
```

Should output:
```
Checking dist/sinas-0.1.0-py3-none-any.whl: PASSED
Checking dist/sinas-0.1.0.tar.gz: PASSED
```

## Test Installation Locally

```bash
# Create a test virtual environment
python3 -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from local wheel
pip install dist/sinas-0.1.0-py3-none-any.whl

# Test basic import
python -c "from sinas import SinasClient; print('Success!')"

# Test FastAPI extras
pip install "dist/sinas-0.1.0-py3-none-any.whl[fastapi]"
python -c "from sinas.integrations.fastapi import SinasAuth; print('FastAPI extras work!')"

# Cleanup
deactivate
rm -rf test_env
```

## Upload to PyPI

### Option 1: Upload to Test PyPI First (Recommended)

Test PyPI is a separate instance for testing package distribution.

```bash
# Upload to Test PyPI
twine upload --repository testpypi dist/*
```

You'll be prompted for:
- Username: `__token__`
- Password: Your Test PyPI API token (starts with `pypi-`)

Then test installation from Test PyPI:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ sinas
```

### Option 2: Upload to Production PyPI

**⚠️ Warning: Once uploaded, you cannot replace or delete a release!**

```bash
# Upload to PyPI
twine upload dist/*
```

You'll be prompted for:
- Username: `__token__`
- Password: Your PyPI API token (starts with `pypi-`)

## Configure PyPI Credentials (Optional)

To avoid entering credentials each time, create `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-YourActualTokenHere

[testpypi]
username = __token__
password = pypi-YourTestPyPiTokenHere
```

**Security**: Ensure this file has restricted permissions:
```bash
chmod 600 ~/.pypirc
```

## After Publishing

1. **Verify on PyPI**: Visit https://pypi.org/project/sinas/
2. **Test Installation**:
   ```bash
   pip install sinas
   pip install sinas[fastapi]
   ```
3. **Create Git Tag**:
   ```bash
   git tag -a v0.1.0 -m "Release version 0.1.0"
   git push origin v0.1.0
   ```
4. **Create GitHub Release** (if using GitHub):
   - Go to repository > Releases > Create new release
   - Tag: `v0.1.0`
   - Title: `SINAS SDK v0.1.0`
   - Description: Copy from CHANGELOG.md

## Updating to a New Version

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` with new changes
3. Rebuild: `python3 -m build`
4. Upload: `twine upload dist/*`

## Troubleshooting

### "File already exists" error
- You cannot re-upload the same version
- Increment the version number in `pyproject.toml`
- Rebuild and upload again

### Import errors after installation
- Check that all dependencies are listed in `pyproject.toml`
- Verify `MANIFEST.in` includes all necessary files
- Test in a clean virtual environment

### "Invalid distribution" error
- Run `twine check dist/*` to see what's wrong
- Common issues: missing README, invalid metadata
- Fix and rebuild

## Package URLs

After publishing:
- **PyPI Page**: https://pypi.org/project/sinas/
- **Test PyPI Page**: https://test.pypi.org/project/sinas/

## Support

If you encounter issues:
1. Check [PyPI packaging guide](https://packaging.python.org/tutorials/packaging-projects/)
2. Review [Twine documentation](https://twine.readthedocs.io/)
3. File an issue on the project repository
