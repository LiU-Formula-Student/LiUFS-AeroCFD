# TODO Before Release (`v1.0`)

Use `- [x]` to mark completed items.

## Release blockers (must be done before tagging `v1.0`)

- [ ] Run full test suite in release env and confirm `42 passed` with no failures.
- [ ] Fix `PytestReturnNotNoneWarning` in `tests/test_error_handling.py::test_error_handling` (replace `return` with assertions).
- [ ] Create and review release notes for `v1.0.0` (breaking changes, install instructions, known limitations).

## Already validated in this branch

- [x] Trusted Publisher (OIDC) is configured and workflow has PyPI publish job.
- [x] Wheel + sdist build successfully (`python -m build`).
- [x] Artifact metadata passes `twine check`.
- [x] README/docs include PyPI install links and extras model (`cli`, `app`, `full`).

## Optional but recommended before `v1.0`

- [x] Add in-app help panel (quick shortcuts + how to load/select runs).
- [x] Add `Report issue / Copy diagnostics` action that copies app/environment/runtime details for bug reports.
- [x] Add a short support matrix (OS + Python versions tested) to the README.
- [x] Add a quick post-install smoke test section (`aerocfd --help`, `python -m aerocfd_app`).
- [x] Pin a reproducible release checklist in `.github` or `docs/` for future releases.
