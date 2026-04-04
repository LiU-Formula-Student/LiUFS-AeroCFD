# Release Checklist for AeroCFD

Use this checklist when preparing a new release (e.g., `v1.0.0`, `v1.1.0`, `v2.0.0-beta.1`).

## Pre-Release (1-2 days before)

- [ ] Run full test suite: `pytest -q`
- [ ] Fix any test failures or warnings
- [ ] Review changelog since last release
- [ ] Update `docs/` if there are UX or API changes
- [ ] Test installation locally: `pip install -e ".[full,dev]"`
- [ ] Smoke test CLI: `aerocfd --help`
- [ ] Smoke test GUI: `python -m aerocfd_app` (load a `.liufs` file if available)
- [ ] Run build: `python -m build`
- [ ] Verify wheel metadata: `python -m twine check dist/*`

## Release Day

### 1. Create Git Tag

```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

**Tag Format:**
- Stable: `v1.0.0`, `v1.2.3`, `v2.0.0`
- Beta/RC: `v1.1.0-beta.1`, `v2.0.0-rc.1`, `v1.0.0-alpha.1`

### 2. Create GitHub Release

- Go to https://github.com/LiU-Formula-Student/LiUFS-AeroCFD/releases
- Click **"Draft a new release"**
- Select tag `vX.Y.Z` (created above)
- Title: "Release v1.0.0" (or appropriate version)
- Add release notes:
  - **Major Changes:** List breaking changes, new features, deprecations
  - **Installation:** Include `pip install "aerocfd[cli]"`, `pip install "aerocfd[app]"`, etc.
  - **Known Issues:** Any known limitations

### 3. Monitor Automated Workflows

**GitHub Actions will automatically:**
1. Build desktop apps for Windows, macOS, Linux
2. Build Python wheel and sdist
3. Publish to PyPI (via Trusted Publisher)
4. Attach artifacts to GitHub release

**Verify:**
- [ ] Check GitHub Actions: all jobs passed (prepare-version, build, build-aerocfd-wheel, publish-to-pypi, publish-release-assets)
- [ ] Check PyPI: https://pypi.org/project/aerocfd/ shows new version
- [ ] Check GitHub Release: artifacts are attached (Windows `.zip`, macOS `.zip`, Linux `.tar.gz`, Python wheel/sdist)

### 4. Test Released Package

```bash
# Install from PyPI
pip install "aerocfd[full]" --upgrade

# Verify version
python -c "from aerocfd_app import __version__; print(__version__)"

# Smoke test
aerocfd --help
python -m aerocfd_app
```

## Post-Release

- [ ] Announce in relevant channels (Discord, email, wiki)
- [ ] Close any "Release v1.0.0" milestone/project on GitHub
- [ ] Update `main` branch docs if needed
- [ ] Plan next sprint/milestone

## Rollback (if needed)

If release is broken:

```bash
# Delete GitHub release (via UI)
# Delete PyPI release (via PyPI admin, marks as yanked)
# Delete Git tag
git tag -d v1.0.0
git push origin --delete v1.0.0
```

## Release Frequency

- **Stable releases** (e.g., `v1.0.0`): When feature-complete and tested
- **Beta/RC releases** (e.g., `v1.1.0-beta.1`): When approaching stable release
- **Patch releases** (e.g., `v1.0.1`): Only for critical bug fixes

## Version Classifier Mapping

The script `scripts/set_app_version.py` automatically updates `Development Status` based on tag:

| Tag Format | Classifier |
|-----------|-----------|
| `v1.0.0`, `v1.2.3` | `5 - Production/Stable` |
| `v1.1.0-beta.1`, `v2.0.0-rc.1` | `4 - Beta` |
| Other formats | `4 - Beta` (conservative default) |

No manual classifier updates needed—handled by release workflow.

## Contact

For release issues or questions, contact the development team via GitHub Issues or LiU Formula Student channels.
