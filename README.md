## Application Workflow

### 1. Direct TOML Handling
If the input file is already a `.toml` file, the application will:
- Validate and format the TOML file using `validate_and_format_toml`.
- Exit the process as no further conversion is required.

### 2. Conditional Setup to CFG Conversion
For input files that are neither `.cfg` nor `.ini`:
- It is assumed the file is a Python setup file (e.g., `setup.py`).
- The file is converted to a `setup.cfg` format using `setup_to_cfg`.

### 3. Format CFG
Independent of the initial format:
- The `setup.cfg` file is formatted using `format_cfg`.

### 4. CFG to TOML Conversion
After formatting:
- The `setup.cfg` file is converted into a `pyproject.toml` file using `cfg_to_toml`.

### 5. Final Validation and Formatting
To conclude the process:
- The newly created `pyproject.toml` file is validated and formatted using `validate_and_format_toml`.