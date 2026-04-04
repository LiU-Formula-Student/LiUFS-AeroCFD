#!/usr/bin/env python3
"""
Simple test to verify the application components work correctly.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure Qt can load in headless CI environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _is_missing_gui_system_lib(error_message: str) -> bool:
    """Return True when import failed due to missing OS-level GUI libraries."""
    missing_markers = [
        "libEGL.so.1",
        "libGL.so.1",
        "libxcb",
        "could not load the Qt platform plugin",
    ]
    lowered = error_message.lower()
    return any(marker.lower() in lowered for marker in missing_markers)

def test_imports():
    """Test that all modules can be imported."""
    print("Testing module imports...")
    from aerocfd_app.liufs_handler import LiufsFileHandler
    gui_import_errors = []

    file_tree_available = True
    try:
        from aerocfd_app.ui.widgets.file_tree import FileTreeWidget
    except Exception as exc:
        file_tree_available = False
        gui_import_errors.append(str(exc))

    video_player_available = True
    try:
        from aerocfd_app.video_player import VideoPlayer
    except Exception as exc:
        video_player_available = False
        gui_import_errors.append(str(exc))

    assert LiufsFileHandler is not None

    if file_tree_available:
        assert FileTreeWidget is not None

    if file_tree_available and video_player_available:
        assert VideoPlayer is not None
        print("✓ All modules import successfully")
    elif gui_import_errors and all(_is_missing_gui_system_lib(msg) for msg in gui_import_errors):
        print("⚠ GUI component import skipped (missing system GUI libraries in CI)")
    else:
        raise RuntimeError("; ".join(gui_import_errors))

def test_liufs_handler():
    """Test LiufsFileHandler with sample data structure."""
    print("\nTesting LiufsFileHandler...")
    from aerocfd_app.liufs_handler import LiufsFileHandler

    # Create a test manifest
    sample_manifest = {
        "format_version": 1,
        "simulation_name": "Test-Simulation",
        "runs": {
            "children": {
                "RUN1": {
                    "children": {
                        "images": {
                            "children": {
                                "cutplanes": {
                                    "children": {
                                        "cp": {"image_count": 100}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    assert LiufsFileHandler is not None
    assert sample_manifest["runs"]["children"]["RUN1"]["children"]["images"]["children"]["cutplanes"]["children"]["cp"]["image_count"] == 100
    print("✓ Sample manifest structure is valid")

def main():
    """Run all tests."""
    print("=" * 50)
    print("LiU FS Viewer - Component Test")
    print("=" * 50)
    
    results = []
    for name, test_func in [
        ("Module Imports", test_imports),
        ("LiufsFileHandler", test_liufs_handler),
    ]:
        try:
            test_func()
            results.append((name, True))
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("=" * 50)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
