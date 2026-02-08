# IDE Configuration for Module Resolution

## Current Setup

The project is configured to properly resolve all module imports including `bleak`, `renogy-ble`, and `pymodbus`.

### Configuration Files

1. **`.vscode/settings.json`** - VSCode/Cursor Python settings
   - Points to the Poetry virtual environment (`.venv`)
   - Adds `src` and `.venv/lib/python3.13/site-packages` to analysis paths
   - Enables Python analysis features

2. **`pyrightconfig.json`** - Pyright/Pylance type checker configuration
   - Explicitly configures the virtual environment path
   - Sets up execution environments with proper paths
   - Configures type checking mode

### Import Strategy

The codebase uses the `TYPE_CHECKING` pattern for conditional imports:

- **Type hints only** (in `if TYPE_CHECKING:` blocks): Used at module level for type annotations
- **Runtime imports** (inside methods): Used when actual functionality is needed

This approach allows:
- Proper type checking in the IDE
- Test mocking without issues
- No circular import problems

### Example Pattern

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bleak import BleakScanner
    from renogy_ble import RenogyBleClient

class BluetoothReader:
    async def _read_implementation(self):
        # Import at runtime for actual use
        from bleak import BleakScanner
        from renogy_ble import RenogyBleClient
        # ... use classes
```

## Troubleshooting Module Warnings

If Cursor/VSCode still shows "module could not be resolved" warnings:

### 1. Verify Python Interpreter

1. Press `Cmd/Ctrl + Shift + P`
2. Type "Python: Select Interpreter"
3. Choose: `Python 3.13.5 (.venv: poetry)`
4. Path should be: `/home/tcronin/src/piSolar/.venv/bin/python`

### 2. Reload Window

1. Press `Cmd/Ctrl + Shift + P`
2. Type "Developer: Reload Window"
3. Wait for the language server to restart

### 3. Verify Dependencies

```bash
# Check that all dependencies are installed
poetry show | grep -E "(bleak|renogy-ble|pymodbus)"

# Should show:
# bleak                 2.1.1
# renogy-ble            1.2.0
# pymodbus              3.11.4
```

### 4. Restart Pylance Language Server

1. Press `Cmd/Ctrl + Shift + P`
2. Type "Pylance: Restart Server"

### 5. Clear Cache (if needed)

```bash
# Clear Python language server cache
rm -rf ~/.cursor/User/workspaceStorage/*/ms-python.python/languageServer.*
```

## Verification

The setup is working correctly if:

1. **All 89 tests pass**: ✅ (confirmed)
2. **No linter errors**: ✅ (confirmed)
3. **Imports work at runtime**: ✅ (confirmed)
4. **Type hints work in IDE**: Should work after selecting interpreter

## Note on Warnings

Some IDEs may still show warnings for imports inside `if TYPE_CHECKING:` blocks when the packages are optional or not yet loaded. This is normal behavior and doesn't affect:
- Code execution
- Tests
- Type checking results

The code is correctly structured and follows Python best practices for conditional imports.
