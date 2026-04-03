# Error Handling Test Files

This directory contains broken `.liufs` files for testing error handling and robustness.

## Files

### Valid File
- **valid_minimal.liufs** - A minimally valid .liufs file with correct structure. Use this to verify the app still works with valid files.

### Invalid/Broken Files

- **empty.liufs** - A ZIP file with no manifest.json. Tests missing manifest detection.
- **invalid_json.liufs** - Contains a manifest.json with invalid JSON syntax. Tests JSON parsing error handling.
- **missing_fields.liufs** - manifest.json is valid JSON but missing required fields (simulation_name, runs). Tests field validation.
- **corrupted.liufs** - A truncated ZIP file that cannot be opened. Tests ZIP corruption detection.
- **broken_runs.liufs** - manifest.json has 'runs' as a string instead of an object. Tests structure validation.
- **invalid_run_structure.liufs** - Contains a run that's not a dictionary. Tests run structure validation.

## How to Test in the UI

1. **Start the application:**
   ```bash
   python app/main.py
   ```

2. **Open a broken file:**
   - Click **File → Open .liufs File** (or press Ctrl+O)
   - Navigate to `tests/broken_liufs_files/`
   - Select any broken file (e.g., `empty.liufs`)

3. **Expected behavior:**
   - A critical error pop-up will appear with a descriptive message
   - The info label will show `❌ Error: ...`
   - The app will remain stable and functional
   - You can try opening another file afterward

4. **Test all files:**
   - Test `valid_minimal.liufs` last to verify the app still works correctly

## Automated Testing

Run the automated test suite:

```bash
python tests/test_error_handling.py
```

This verifies that all broken files correctly raise `LiufsValidationError` with meaningful error messages.

## Error Messages

Each error now includes:
- **What went wrong** (e.g., "manifest.json not found")
- **Why it matters** (e.g., "This file may have been created with an older or incompatible version")
- **Technical details** (for advanced users/debugging)

## Adding New Test Cases

To add a broken file for a new error scenario:

```python
import json
import zipfile

# Your scenario here
with zipfile.ZipFile('new_error.liufs', 'w') as zf:
    manifest = {
        # Your broken structure
    }
    zf.writestr('manifest.json', json.dumps(manifest))
```

Then update the test script and this documentation.
