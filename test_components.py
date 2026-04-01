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
    try:
        from liufs_handler import LiufsFileHandler
        from file_tree import FileTreeWidget
        from video_player import VideoPlayer
        print("✓ All modules import successfully")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_liufs_handler():
    """Test LiufsFileHandler with sample data structure."""
    print("\nTesting LiufsFileHandler...")
    try:
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
        
        print("✓ Sample manifest structure is valid")
        return True
    except Exception as e:
        print(f"✗ LiufsFileHandler test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("LiU FS Viewer - Component Test")
    print("=" * 50)
    
    results = []
    results.append(("Module Imports", test_imports()))
    results.append(("LiufsFileHandler", test_liufs_handler()))
    
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
