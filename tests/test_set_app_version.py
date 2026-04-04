from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.set_app_version import classifier_for_tag, to_pep440


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v1.0.0", "1.0.0"),
        ("v1.2.3", "1.2.3"),
        ("v1.1.0-beta.1", "1.1.0b1"),
        ("v2.0.0-rc.1", "2.0.0rc1"),
        ("v1.0-beta-0.1", "1.0b0.post1"),
    ],
)
def test_to_pep440_expected_tag_mappings(tag: str, expected: str) -> None:
    assert to_pep440(tag) == expected


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v1.0.0", "Development Status :: 5 - Production/Stable"),
        ("v1.2.3", "Development Status :: 5 - Production/Stable"),
        ("v1.1.0-beta.1", "Development Status :: 4 - Beta"),
        ("v2.0.0-rc.1", "Development Status :: 4 - Beta"),
        ("v1.0.0-alpha.1", "Development Status :: 4 - Beta"),
    ],
)
def test_classifier_for_tag_expected_tag_mappings(tag: str, expected: str) -> None:
    assert classifier_for_tag(tag) == expected
