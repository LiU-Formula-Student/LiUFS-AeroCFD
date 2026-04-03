# Error Messages Reference

This document shows example error messages and what they mean.

## File Opening Errors

### 1. File Not Found
```
[Pop-up Dialog]
Error: File Not Found

The file could not be found.

/path/to/file.liufs (No such file or directory)

[OK]
```
**What it means**: The file path you provided doesn't exist.  
**How to fix**: Check the file path, make sure the file hasn't been moved or deleted.

---

### 2. Invalid .liufs File (Missing Manifest)
```
[Pop-up Dialog]
Error: Invalid .liufs File

This file is not a valid .liufs archive.

Invalid .liufs file: manifest.json not found at root.

This file may have been created with an older or incompatible version.

[OK]
```
**What it means**: The file doesn't contain the required manifest.json.  
**How to fix**: Re-create the .liufs file using the current version of the compressor.

---

### 3. Invalid JSON Manifest
```
[Pop-up Dialog]
Error: Invalid .liufs File

This file is not a valid .liufs archive.

manifest.json is corrupted or contains invalid JSON.

Details: Expecting property name enclosed in double quotes...

[OK]
```
**What it means**: The manifest.json file is malformed.  
**How to fix**: The file may be corrupted. Try creating it again.

---

### 4. Missing Required Fields
```
[Pop-up Dialog]
Error: Invalid .liufs File

This file is not a valid .liufs archive.

manifest.json is incomplete: missing fields ['runs', 'simulation_name'].

[OK]
```
**What it means**: The manifest is missing essential information.  
**How to fix**: Re-create the .liufs file with the current compressor version.

---

### 5. Unsupported Format Version
```
[Pop-up Dialog]
Error: Invalid .liufs File

This file is not a valid .liufs archive.

Unsupported .liufs format version: 2 (this application supports version 1).

[OK]
```
**What it means**: The file was created with a newer version.  
**How to fix**: Update the viewer application to the latest version.

---

### 6. Corrupted ZIP File
```
[Pop-up Dialog]
Error: Invalid .liufs File

This file is not a valid .liufs archive.

File is corrupted or not a valid .liufs archive.

Details: Not a valid ZIP file.

[OK]
```
**What it means**: The file is damaged or not a .liufs file.  
**How to fix**: Make sure the file downloaded completely and wasn't corrupted during transfer.

---

## Media Loading Warnings

### Issues while loading media appear in the Info Label

```
[Info Label]
⚠ Warning: Video path not found in manifest
```
**What it means**: The video file referenced in the manifest doesn't exist in the archive.  
**How to fix**: Recreate the .liufs file - the archive may be corrupted.

---

```
[Info Label]
❌ Error: Video file not found in archive
  Path: runs/RUN1/images/cutplanes/cp.mp4
```
**What it means**: A specific video file is missing.  
**How to fix**: Check if the file was properly included when creating the .liufs.

---

```
[Info Label]
❌ Error: Cannot play video
  This may be a codec issue or corrupted video file.
  Details: [codec error details]
```
**What it means**: The video file exists but can't be played (codec issue or corruption).  
**How to fix**: 
- Try a different video/category
- Re-create the .liufs file with proper video encoding

---

```
[Info Label]
❌ Error: Cannot read image file
  The file may be corrupted or in an unsupported format
```
**What it means**: An image file can't be decoded.  
**How to fix**: The file may be corrupted or in an unsupported format.

---

## Operation Warnings

### Adding Runs
```
[Info Label]
⚠ Warning: A run named 'RUN_NAME' already exists.
  Existing runs: RUN1, RUN2, RUN3
```
**What it means**: You're trying to add a run with a name that already exists.  
**How to fix**: Either rename the run or skip adding it.

---

## Success Messages

```
[Info Label]
✓ File loaded successfully
  Simulation: CFD-Aerodynamics-v2
  Runs: LOW_FRH, LOW_RRH, NORMAL_CONDITION
```
**What it means**: File opened successfully and is ready to use.

---

```
[Info Label]
✓ Loaded: cutplanes/cp/plane_0001
  Frames: 287 | FPS: 12.00
```
**What it means**: Video loaded successfully with frame count and playback info.

---

```
[Info Label]
✓ Loaded: surfaces/cp/visualization.png
  Size: 1920x1080 px
```
**What it means**: Image loaded successfully with dimensions.

---

## Error Message Format

All error messages follow this pattern:

1. **Title** (what category of error)
2. **Description** (what went wrong in plain language)
3. **Technical Details** (for debugging/support)
4. **Recovery Suggestion** (implied or explicit)

## How to Report Errors

If you encounter an error message not listed here:

1. Take a screenshot of the error dialog
2. Note down the **exact error message**
3. Note what you were trying to do
4. Report to: [your support channel/email]

Include:
- Error message (full text)
- File name/path
- Steps to reproduce
- Operating system
- Application version (Help → Info)
