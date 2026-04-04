# Python 3.12 Setup Instructions
> HyperReal 3D Render Pipeline — required for Open3D compatibility

## Why 3.12?

Open3D (our core mesh library) has no wheels for Python 3.13+. The pipeline will fail to import `open3d` on any newer version. This is a hard blocker for Session 1A (loading real meshes).

## Recommended: Python.org Installer (5 minutes)

This is the fastest path. No extra tooling needed.

1. **Download Python 3.12.x** from https://www.python.org/downloads/release/python-31210/
   - Scroll to "Files" at bottom
   - Download **Windows installer (64-bit)** (`python-3.12.10-amd64.exe`)

2. **Run the installer**
   - **Uncheck** "Add Python 3.12 to PATH" (you already have 3.14 on PATH — don't conflict)
   - Click "Customize installation"
   - Check all Optional Features, click Next
   - Under Advanced Options, check "Install for all users" (puts it in `C:\Program Files\Python312\`)
   - Click Install

3. **Verify it installed**
   ```bash
   py -3.12 --version
   # Should print: Python 3.12.10
   ```
   The `py` launcher (already on your system) auto-discovers installed Python versions.

4. **Create the project venv**
   ```bash
   cd C:/Users/admin/Desktop/HyperReal/3d-render-pipeline-core
   py -3.12 -m venv .venv
   ```

5. **Activate and install deps**
   ```bash
   # In Git Bash:
   source .venv/Scripts/activate
   
   # Verify:
   python --version  # Should show 3.12.x
   
   # Install dependencies:
   pip install -r requirements.txt
   ```

6. **Set VS Code interpreter**
   - Open the project in VS Code
   - `Ctrl+Shift+P` → "Python: Select Interpreter"
   - Choose the `.venv` entry (should show `Python 3.12.x`)
   - This also makes the VS Code terminal auto-activate the venv

## Verify Everything Works

```bash
# With venv activated:
python -c "import open3d; print(open3d.__version__)"
python -c "import trimesh; print(trimesh.__version__)"
python -c "import manifold3d; print('manifold3d OK')"
pytest tests/ -v
```

All 29 tests should pass, and all three imports should succeed.

## Alternative: pyenv-win

If you want to manage multiple Python versions long-term:

```bash
# Install pyenv-win (PowerShell, admin):
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"

# Then:
pyenv install 3.12.10
pyenv local 3.12.10
python -m venv .venv
```

This is more setup but useful if you'll juggle multiple Python projects. For this repo alone, the direct installer above is faster.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `py -3.12` not found after install | Restart terminal. The `py` launcher reads the registry, not PATH. |
| `pip install open3d` fails | Verify `python --version` shows 3.12.x inside the venv. Open3D won't install on 3.13+. |
| `manifold3d` build fails | Should install from wheel. If not: `pip install --upgrade pip` first, then retry. |
| VS Code uses wrong Python | Check bottom-left interpreter indicator. Click it to switch. |
| `.venv` already exists (stale) | Delete it and recreate: `rm -rf .venv && py -3.12 -m venv .venv` |
