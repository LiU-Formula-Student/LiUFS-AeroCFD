#!/usr/bin/env python3
"""
Test script to verify error handling with various broken .liufs files.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aerocfd_app.liufs_handler import LiufsFileHandler, LiufsValidationError


def test_error_handling():
    """Test error handling with broken .liufs files."""
    test_dir = Path(__file__).resolve().parent / "broken_liufs_files"
    
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        return False
    
    test_files = {
        "empty.liufs": "Empty ZIP (no manifest)",
        "invalid_json.liufs": "Invalid JSON in manifest",
        "missing_fields.liufs": "Missing required fields",
        "corrupted.liufs": "Corrupted ZIP file",
        "broken_runs.liufs": "Broken runs node",
        "invalid_run_structure.liufs": "Invalid run structure",
        "valid_minimal.liufs": "Valid minimal structure",
        "skipped_unknown_run.liufs": "Mixed file with skipped unknown run",
    }

    expected_success = {"valid_minimal.liufs", "skipped_unknown_run.liufs"}
    
    print("=" * 70)
    print("Testing Error Handling with Broken .liufs Files")
    print("=" * 70)
    
    results = []
    
    for filename, description in test_files.items():
        file_path = test_dir / filename
        
        if not file_path.exists():
            print(f"\n⚠ Skipping {filename} (not found)")
            results.append((filename, "SKIP", "File not found"))
            continue
        
        try:
            handler = LiufsFileHandler(str(file_path))
            
            if filename in expected_success:
                # This should succeed
                print(f"\n✓ {filename}")
                print(f"  Description: {description}")
                print(f"  Simulation: {handler.get_simulation_name()}")
                print(f"  Runs: {handler.get_runs()}")

                if filename == "skipped_unknown_run.liufs":
                    warnings = handler.get_validation_warnings()
                    print(f"  Warnings: {warnings}")
                    assert handler.get_runs() == ["NORMAL_CONDITION"]
                    assert any("ROLL_2deg" in warning for warning in warnings)

                results.append((filename, "PASS", "Successfully loaded"))
            else:
                # This should have failed
                print(f"\n❌ {filename}")
                print(f"  Description: {description}")
                print(f"  ERROR: Should have raised LiufsValidationError but succeeded!")
                results.append((filename, "FAIL", "Did not raise expected error"))
        
        except LiufsValidationError as e:
            if filename not in expected_success:
                print(f"\n✓ {filename}")
                print(f"  Description: {description}")
                print(f"  Correctly raised LiufsValidationError:")
                # Show first 100 chars of error
                error_msg = str(e)[:100]
                print(f"  {error_msg}{'...' if len(str(e)) > 100 else ''}")
                results.append((filename, "PASS", "Correctly raised error"))
            else:
                print(f"\n❌ {filename}")
                print(f"  Description: {description}")
                print(f"  ERROR: Valid file raised unexpected error!")
                print(f"  {str(e)}")
                results.append((filename, "FAIL", "Valid file raised error"))
        
        except Exception as e:
            print(f"\n❌ {filename}")
            print(f"  Description: {description}")
            print(f"  ERROR: Unexpected exception type: {type(e).__name__}")
            print(f"  {str(e)}")
            results.append((filename, "FAIL", f"Unexpected {type(e).__name__}"))
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    skipped = sum(1 for _, status, _ in results if status == "SKIP")
    
    for filename, status, message in results:
        symbol = "✓" if status == "PASS" else "❌" if status == "FAIL" else "⊘"
        print(f"{symbol} {filename:30s} {status:6s} - {message}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    return failed == 0


if __name__ == "__main__":
    success = test_error_handling()
    sys.exit(0 if success else 1)
