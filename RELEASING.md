# Releasing `psqlomni`

This project publishes to PyPI via GitHub Actions using PyPI Trusted Publishing.

## One-time setup

1. In GitHub, create an environment named `pypi`.
2. Add protection rules to `pypi` (recommended: require at least one reviewer).
3. In PyPI (`psqlomni` project), add a Trusted Publisher with:
   - Owner: `emmakodes`
   - Repository: `psqlomni`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

## Release flow

1. Ensure CI on `main` is green.
2. Bump version in `pyproject.toml` (SemVer).
3. Merge the version bump to `main`.
4. Create and push a tag for that version:
   - `git tag vX.Y.Z`
   - `git push origin vX.Y.Z`
5. GitHub Actions `Release` workflow will:
   - run lint + tests on Python 3.10/3.11/3.12
   - verify tag equals package version
   - build and validate distributions
   - publish to PyPI

## Notes

- Tag and package versions must match exactly (for example `v0.1.3` and `0.1.3`).
- If a publish fails after version/tag creation, fix forward with a new version and tag.
