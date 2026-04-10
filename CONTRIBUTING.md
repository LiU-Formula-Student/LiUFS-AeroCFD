# Contributing to AeroCFD

Thanks for contributing.

This document describes the development workflow for this repository.

## Branching model

Protected long-lived branches:
- `main` (production-ready, release branch)
- `develop` (integration branch, default for normal work)

Working branch naming conventions:
- `docs/<short-description>`
- `bugfix/<short-description>`
- `features/<short-description>`

Examples:
- `docs/update-readme-installation`
- `bugfix/fix-liufs-manifest-parse`
- `features/add-sequence-playback-toggle`

## Where to branch from

- Normal work: branch from `develop`
- Hotfix work: branch from `main` (typically `bugfix/*`)

## Where to merge

- Normal path: open PR into `develop`
- Hotfix path: open PR into `main`

After a hotfix merge to `main`, open a follow-up PR from `main` to `develop` to keep branches in sync.

## Pull requests

Use the repository PR templates:
- Feature: `.github/PULL_REQUEST_TEMPLATE/feature.md`
- Bugfix: `.github/PULL_REQUEST_TEMPLATE/bugfix.md`
- Docs/Chore: `.github/PULL_REQUEST_TEMPLATE/docs_chore.md`

PR expectations:
- Keep PR scope focused and small
- Link related issue(s)
- Describe root cause (for bugfixes)
- Include validation steps and outcomes
- Update docs when behavior changes

## Local development setup

Requirements:
- Python 3.12+
- FFmpeg

Install dependencies:

```bash
pip install -e ".[full,dev]"
```

## Running locally

Run the desktop app:

```bash
python -m aerocfd_app
```

CLI help:

```bash
aerocfd --help
```

## Tests and checks

Run tests before opening PR:

```bash
python -m tests
```

If you changed packaging/build logic, also run the relevant platform build script in `scripts/`.

## Commit message style

Use clear, scoped commit messages. Examples:
- `docs: update contribution guide`
- `fix(parser): handle missing run metadata`
- `feat(viewer): add keyboard shortcut for play/pause`

## Recognition and Authors

Contributors with substantial, sustained impact may be added to the Authors section in `README.md`.

Examples of substantial contribution include one or more of:
- Significant code contributions across multiple PRs
- Meaningful architecture, reliability, or performance improvements
- Ongoing high-quality review and maintenance work
- Major documentation or release-process improvements

Decision process:
- Maintainers decide by consensus
- Any maintainer or contributor may propose an addition in a PR
- The PR should include a short rationale and links to representative contributions

Author entry format in `README.md`:
- `Full Name — [GitHub Profile](https://github.com/<username>)`
- Keep one person per line for consistency

## Code of conduct

Be respectful and constructive in discussions and reviews.
