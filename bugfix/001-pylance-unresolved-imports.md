# 001 — Pylance: "could not be resolved" on imports

**Status:** fixed · **Date:** 2026-11-05 · **Severity:** cosmetic (editor only — code always ran)

## Bug

VS Code underlined most imports in `tests/test_project.py` with two different messages:

| Import | Message | Code |
|---|---|---|
| `pandas`, `matplotlib` | Import "X" could not be resolved **from source** | `reportMissingModuleSource` |
| `pytest`, `streamlit.testing.v1` | Import "X" could not be resolved | `reportMissingImports` |
| `utils`, `main` | Import "X" could not be resolved | `reportMissingImports` |
| `numpy` | *(no warning)* | — |

Warnings only: `python -m pytest tests/ -v` passed the whole time.

## Cause

Two independent causes that produced the same-looking squiggle.

**1. Wrong interpreter selected.** Pylance was analysing with the global
interpreter (`...\Python\pythoncore-3.14-64`), whose `site-packages` contains
only `numpy`. Every project dependency lives in `.venv` instead.

That `numpy` was the one clean import is the giveaway. It also explains the two
wordings: Pylance bundles type stubs for `pandas` and `matplotlib`, so it could
type-check them but found no package behind the stubs ("from source"); `pytest`
and `streamlit` have no bundled stubs, so there was nothing at all.

**2. `src/` not on the analysis path.** `utils` and `main` resolve at runtime
only because of `sys.path.insert(0, str(SRC_DIR))` in `tests/test_project.py:48`
(same trick in `src/main.py:48`, `src/app.py:31`). A static analyser never
executes that line, so it cannot know `src/` is an import root.

**Not the cause:** missing packages. All 10 entries of `requirements.txt` were
already installed in `.venv`. Re-running `pip install -r requirements.txt` fixes
nothing — and could never fix `utils`/`main`, which are local modules.

## Fix

Created `.vscode/settings.json` at the **workspace root** (`0926_ds_thebridge_ft`),
not in the project folder — the workspace is the course repo and the venv sits
four levels down, which is why nothing was auto-detected:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/2-Analytics/EDA/my-eda-project/.venv/Scripts/python.exe",
  "python.analysis.extraPaths": ["2-Analytics/EDA/my-eda-project/src"],
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["2-Analytics/EDA/my-eda-project/tests"],
  "python.testing.cwd": "${workspaceFolder}/2-Analytics/EDA/my-eda-project"
}
```

`extraPaths` clears cause 2. For cause 1 the file is not enough on its own —
`defaultInterpreterPath` only applies when no interpreter has been explicitly
chosen, so the stale global selection had to be replaced by hand:

1. Open a `.py` file (not a notebook — a notebook's status bar shows the Jupyter
   *kernel* picker, which is a different setting).
2. Click the Python version in the status bar, bottom right.
3. **Enter interpreter path** → `...\my-eda-project\.venv\Scripts\python.exe`
4. `Ctrl+Shift+P` → **Developer: Reload Window** (Pylance caches aggressively).

Both interpreters are Python 3.14, so the picker lists two near-identical
entries — pasting the path avoids choosing the wrong one.

## Verify

All import warnings gone from `tests/test_project.py`; `pytest` still green.
