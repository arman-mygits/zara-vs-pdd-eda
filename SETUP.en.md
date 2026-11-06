# 🛠️ Installation and usage guide

> 🌍 **English** · [Español](SETUP.md)

A step-by-step guide to getting this project running on **any machine**, from
scratch. No prior knowledge of virtual environments assumed — everything is
explained.

Estimated time: **5–10 minutes** (mostly waiting for packages to install).

---

## Contents

1. [What you need](#1-what-you-need)
2. [Install Python](#2-install-python)
3. [Get the project](#3-get-the-project)
4. [Create the virtual environment](#4-create-the-virtual-environment)
5. [Install the libraries](#5-install-the-libraries)
6. [Run the analysis](#6-run-the-analysis)
7. [Open the report (Jupyter)](#7-open-the-report-jupyter)
8. [Launch the interactive demo (Streamlit)](#8-launch-the-interactive-demo-streamlit)
9. [Common problems](#9-common-problems)
10. [Command cheat sheet](#10-command-cheat-sheet)

---

## 1. What you need

| | Minimum | Note |
|---|---|---|
| **Python** | 3.10 or newer | Tested on 3.14 |
| **Disk space** | ~500 MB | Almost all of it is the libraries |
| **Internet** | First time only | To install packages and download the data |

> **No internet?** The project ships with cached data in `src/data/raw/`, so it
> works fully offline. Skip to step 6.

---

## 2. Install Python

### Already have it?

Open a terminal and type:

```bash
python --version
```

If it answers `Python 3.10.x` or newer, **skip to step 3**.

<details>
<summary>How do I open a terminal?</summary>

* **Windows:** press `Windows` → type `powershell` → Enter
* **macOS:** `Cmd + Space` → type `terminal` → Enter
* **Linux:** `Ctrl + Alt + T`
</details>

### If you don't have it

**Windows**
1. Download from [python.org/downloads](https://www.python.org/downloads/)
2. ⚠️ **CRITICAL:** on the installer's first screen, tick **"Add Python to
   PATH"**. If you miss it, your terminal won't find Python and nothing below
   will work.
3. Click *Install Now*

**macOS**
```bash
brew install python
```
(No Homebrew? Download from [python.org](https://www.python.org/downloads/))

**Linux (Ubuntu/Debian)**
```bash
sudo apt update && sudo apt install python3 python3-venv python3-pip
```

---

## 3. Get the project

**Option A — with Git:**
```bash
git clone <REPOSITORY-URL>
cd 0926_ds_thebridge_ft/2-Analytics/EDA/my-eda-project
```

**Option B — without Git:** download the ZIP from GitHub, extract it, and open
a terminal **inside the `my-eda-project` folder**.

> ### ⚠️ The single most common mistake
> Every command in this guide runs from the **`my-eda-project`** folder (the
> one containing `requirements.txt`). Check with:
>
> ```bash
> # Windows
> dir requirements.txt
> # macOS / Linux
> ls requirements.txt
> ```
>
> If it says "file not found", you're in the wrong folder. Use `cd` to navigate
> to wherever `requirements.txt` lives.

---

## 4. Create the virtual environment

A **virtual environment** is a folder holding the libraries for *this* project
only, without touching your system Python or any other project. No version
conflicts, ever.

```bash
python -m venv .venv
```

This creates a hidden `.venv/` folder. Now **activate** it:

**Windows (PowerShell)**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (CMD)**
```cmd
.venv\Scripts\activate.bat
```

**Windows (Git Bash / MINGW64)**
```bash
source .venv/Scripts/activate
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

> ### ⚠️ Using Git Bash on Windows? Read this
> Git Bash is a hybrid case: a Unix shell, but the virtual environment was
> created by Windows Python. That's why **neither** of these works:
>
> ```bash
> .\.venv\Scripts\Activate.ps1   # ❌ in bash, \ escapes characters, so this
>                                #    collapses into "..venvScriptsActivate.ps1"
> source .venv/bin/activate      # ❌ bin/ is the macOS/Linux layout;
>                                #    on Windows it's Scripts/
> ```
>
> The correct one mixes both: forward slashes **and** `Scripts/`, pointing at
> the extension-less `activate` file:
>
> ```bash
> source .venv/Scripts/activate  # ✅
> ```

### How do I know it worked?

Your terminal prompt now starts with `(.venv)`:

```
(.venv) C:\...\my-eda-project>
```

That `(.venv)` is the signal everything is fine. **It must be there every time
you run something.** Close the terminal and you'll need to activate it again.

<details>
<summary>⚠️ Windows: "running scripts is disabled on this system"</summary>

PowerShell blocks scripts by default. Run this **once** and retry the
activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

It affects your user account only, and it's Microsoft's recommended setting for
development.
</details>

---

## 5. Install the libraries

With the environment active (`(.venv)` visible):

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Takes **2–5 minutes**. Lots of output scrolling past is normal.

### Check everything landed

```bash
python -c "import pandas, numpy, scipy, matplotlib, seaborn, yfinance, streamlit; print('All OK')"
```

If it prints `All OK`, you're ready. ✅

---

## 6. Run the analysis

This is the main command. It runs the **entire** pipeline: download, cleaning,
feature engineering, hypothesis tests and the four charts.

```bash
python src/main.py
```

<details>
<summary>What you'll see</summary>

```
==============================================================================
STEP A | INGESTION, DATA HYGIENE AUDIT AND CALENDAR ALIGNMENT
==============================================================================
  [AUDIT] A1. raw Adj Close (union calendar)   shape=(991, 3)  d_rows= -
  ...
  >>> A blanket .dropna() would have destroyed 35 rows (3.5% of the sample).
  ...
VERDICTS | WHAT THE DATA SAYS ABOUT EACH PRE-STATED HYPOTHESIS
  H1 ... NOT SUPPORTED (data points the other way)
  H2 ... SUPPORTED (direction + statistically significant)
  H3 ... SUPPORTED (direction + statistically significant)
```
</details>

### Useful variants

| Command | What it does |
|---|---|
| `python src/main.py` | Downloads fresh data from Yahoo Finance |
| `python src/main.py --offline` | **No internet.** Uses the cache in `src/data/raw/` |
| `python src/main.py --no-charts` | Tables only, no images (faster) |

### What it produces

```
reports/figures/     4 PNG charts at 300 DPI (the PowerPoint ones)
reports/tables/      16 markdown tables + the audit ledger
src/data/processed/  4 analysis-ready CSVs
src/data/raw/        the original download, cached
```

> 💡 **For presentation day:** run `python src/main.py` the night before. After
> that always use `--offline`, so you never depend on the venue's wifi.

---

## 7. Open the report (Jupyter)

The report (`src/memoria.ipynb`) **ships already executed**, with every result
saved inside. You can read it straight on GitHub without installing anything.

To open and re-run it:

```bash
jupyter lab src/memoria.ipynb
```

### If you use VS Code

1. Open `src/memoria.ipynb`
2. Top right, click the **kernel selector**
3. Choose *Python Environments* → the one labelled **`.venv`**

> ⚠️ Pick the system Python instead of the `.venv` and **every cell will fail**
> with `ModuleNotFoundError: No module named 'pandas'`. This is the number-one
> notebook problem: the libraries live in the virtual environment, not in your
> global Python.

---

## 8. Launch the interactive demo (Streamlit)

```bash
streamlit run src/app.py
```

It opens in your browser automatically at `http://localhost:8501`.

> **Note:** the app's interface is in Spanish (the evaluation panel's language).
> The tab guide below maps it out.

| Tab | Contents |
|---|---|
| 📊 **Resumen** (Summary) | KPIs and the verdict on all three hypotheses |
| 📈 **H1 · Rendimiento** (Performance) | Growth chart + alpha tests |
| ⚠️ **H2 · Riesgo** (Risk) | Distributions + a **live-adjustable** crash threshold |
| 🔊 **H3 · Liquidez** (Liquidity) | Volume seasonality, Zara vs Temu |
| 🔗 **Síntesis** (Synthesis) | Correlation matrices by regime |
| 🧹 **Higiene de datos** (Data hygiene) | The audit ledger and cleaning decisions |

### Two tricks for the defence

* **The robustness check:** tick *"Solo sesiones reales"* (real sessions only)
  in the sidebar. It excludes every forward-filled day and H2's conclusion
  doesn't change — that's your answer to *"what if your data cleaning is
  creating the result?"*.
* **The crash threshold:** drag it to −10%. Zara stays at **0 sessions**, Temu
  at **12**. That's the slide that explains itself.

> **To stop the app:** `Ctrl + C` in the terminal.

> ⚠️ The app **only reads** the pipeline's results, it doesn't compute them. If
> you get *"No hay datos procesados todavía"* (no processed data yet), run step
> 6 first.

---

## 9. Common problems

<details>
<summary><b>"python is not recognized as a command"</b> (Windows)</summary>

You didn't tick *"Add Python to PATH"* during installation. Two fixes:
* Reinstall Python with that box ticked, **or**
* Use `py` instead of `python` in every command.
</details>

<details>
<summary><b>"ModuleNotFoundError: No module named 'pandas'"</b></summary>

The virtual environment isn't active. Check whether your prompt starts with
`(.venv)`. If not, go back to **step 4** and activate it.

In a VS Code notebook, it means you picked the wrong kernel — see step 7.
</details>

<details>
<summary><b>"No module named 'tabulate'" or similar</b></summary>

Missing libraries. With the environment active:
```bash
python -m pip install -r requirements.txt
```
</details>

<details>
<summary><b>The Yahoo Finance download fails or comes back empty</b></summary>

It happens: it's a free public API and it sometimes rate-limits. Use the
bundled cache:
```bash
python src/main.py --offline
```
If the error mentions `database is locked`, that's `yfinance`'s SQLite cache.
The project already downloads serially (`threads=False`) to avoid it — just
retry.
</details>

<details>
<summary><b>"Port 8501 is already in use"</b> (Streamlit)</summary>

An app is already running. Close it with `Ctrl + C`, or use another port:
```bash
streamlit run src/app.py --server.port 8502
```
</details>

<details>
<summary><b>Charts show boxes instead of text</b></summary>

The *Segoe UI* font is missing. The code already falls back to *DejaVu Sans*,
but if you see tofu boxes, clear the matplotlib cache:
```bash
python -c "import matplotlib; import shutil; shutil.rmtree(matplotlib.get_cachedir())"
```
</details>

<details>
<summary><b>I want to start over</b></summary>

Delete the `.venv/` folder and repeat from step 4. Nothing is lost: the code
and the data live outside the environment.
</details>

---

## 10. Command cheat sheet

```bash
# --- FIRST TIME ONLY --------------------------------------------
python -m venv .venv                       # create the environment
.\.venv\Scripts\Activate.ps1               # activate (Windows PowerShell)
source .venv/Scripts/activate              # activate (Windows Git Bash)
source .venv/bin/activate                  # activate (macOS / Linux)
python -m pip install -r requirements.txt  # install libraries

# --- EVERY NEW TERMINAL SESSION ---------------------------------
.\.venv\Scripts\Activate.ps1               # Windows PowerShell
source .venv/Scripts/activate              # Windows Git Bash
source .venv/bin/activate                  # macOS / Linux

# --- RUNNING THE PROJECT ----------------------------------------
python src/main.py                         # full analysis (needs internet)
python src/main.py --offline               # analysis from the cache
streamlit run src/app.py                   # interactive demo
jupyter lab src/memoria.ipynb              # open the report
python -m pytest tests/ -v                 # verify everything works
```

---

Something not working? Open an issue on the repository with your operating
system, your Python version (`python --version`) and the full error message.
