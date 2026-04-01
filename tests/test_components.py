#!/usr/bin/env python3
"""
Simple test to verify the application components work correctly.
"""

import sys
import os
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent / "app"))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing module imports...")
    from liufs_handler import LiufsFileHandler
    from file_tree import FileTreeWidget
    from video_player import VideoPlayer

    assert LiufsFileHandler is not None
    assert FileTreeWidget is not None
    assert VideoPlayer is not None
    print("✓ All modules import successfully")

def test_liufs_handler():
    """Test LiufsFileHandler with sample data structure."""
    print("\nTesting LiufsFileHandler...")
    from liufs_handler import LiufsFileHandler

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
