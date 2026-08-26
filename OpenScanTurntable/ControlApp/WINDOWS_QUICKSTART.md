# ControlApp — Windows Quick Start (support branch)

Use this guide if you need to run **ControlApp** from the `support/controlapp` branch on Windows.

You can clone with **GitHub CLI (`gh`)** (recommended if you have it) or with **git only**.

## Prerequisites

1. **Git for Windows** — [https://git-scm.com/download/win](https://git-scm.com/download/win)  
   During install, keep the option that adds Git to PATH.

2. **GitHub CLI (`gh`)** — optional, but useful for auth and cloning. Confirm with `gh --version`.  
   If you use `gh` and are not logged in yet: `gh auth login` (follow the prompts; choose HTTPS).

3. **Python 3.8 or later** — [https://www.python.org/downloads/](https://www.python.org/downloads/)  
   On the installer first screen, check **Add python.exe to PATH**.

4. USB connection from the PC to the Arduino / CNC controller (after hardware is assembled).

Verify in **Command Prompt** or **PowerShell**:

```bat
git --version
python --version
```

Optional (if using `gh`):

```bat
gh --version
gh auth status
```

You should see Git and Python 3.8+ versions. If `python` is not found, try `py --version` instead.

## 1. Clone the repository

Open **Command Prompt** or **PowerShell**. Pick **one** of the methods below.

If you already cloned the repo earlier, skip cloning and just `cd` into the existing folder, then continue with section 2.

### Option A — using `gh` (recommended)

You will be given a repository name in the form `owner/3d-scanner-toolbox`:

```bat
cd %USERPROFILE%\Documents
gh repo clone owner/3d-scanner-toolbox -- -b support/controlapp
cd 3d-scanner-toolbox
```

Replace `owner/3d-scanner-toolbox` with the exact repo name you were given.  
The `-- -b support/controlapp` part clones and checks out the support branch in one step.

Without the branch flag:

```bat
cd %USERPROFILE%\Documents
gh repo clone owner/3d-scanner-toolbox
cd 3d-scanner-toolbox
git fetch origin
git checkout support/controlapp
```

### Option B — git only (no `gh`)

You will be given a clone URL (HTTPS). Then:

```bat
cd %USERPROFILE%\Documents
git clone <CLONE_URL>
cd 3d-scanner-toolbox
git fetch origin
git checkout support/controlapp
```

Replace `<CLONE_URL>` with the URL you were given.

To clone the support branch directly:

```bat
cd %USERPROFILE%\Documents
git clone -b support/controlapp --single-branch <CLONE_URL>
cd 3d-scanner-toolbox
```

If Git asks for credentials over HTTPS, sign in with your GitHub account (or a personal access token if prompted for a password).

## 2. Confirm the support branch

```bat
git branch
git status
```

You should see `* support/controlapp` and that the branch is up to date with `origin/support/controlapp`.

If you are on another branch:

```bat
git fetch origin
git checkout support/controlapp
git pull
```

## 3. Run ControlApp

```bat
cd OpenScanTurntable\ControlApp
run.bat
```

`run.bat` will:

- Check that Python 3.8+ is available
- Install dependencies from `requirements.txt` if needed
- Start the ControlApp GUI (`main.py`)

### Alternative (manual)

```bat
cd OpenScanTurntable\ControlApp
python -m pip install -r requirements.txt
python main.py
```

If `python` does not work, use:

```bat
py -m pip install -r requirements.txt
py main.py
```

## 4. Connect to the turntable

1. Plug in the Arduino / CNC shield over USB.
2. In the ControlApp window, select the correct **COM port** (e.g. `COM3`).
3. Connect and verify status / movement from the GUI.

If no COM port appears, open Windows **Device Manager** → **Ports (COM & LPT)** and install the Arduino USB driver if needed.

## 5. Update after new changes are committed

When you are told that fixes were pushed to `support/controlapp`, pull them and restart the app.  
Updating uses **git only** (same steps whether you originally cloned with `gh` or `git`):

1. Close ControlApp if it is running.
2. Open **Command Prompt** or **PowerShell**.
3. Go to the repo and update:

```bat
cd %USERPROFILE%\Documents\3d-scanner-toolbox
git checkout support/controlapp
git fetch origin
git pull
```

4. Confirm you have the latest commits (optional):

```bat
git log -3 --oneline
```

5. Start the app again:

```bat
cd OpenScanTurntable\ControlApp
run.bat
```

Notes:

- Always stay on `support/controlapp` for this support work — do not switch to `main` unless asked.
- If `git pull` reports local conflicts or modified files you did not mean to change, stop and ask for help before continuing.
- If dependencies change, `run.bat` will reinstall them as needed; you can also run `python -m pip install -r requirements.txt` manually.
- If `git pull` fails with an auth error and you use `gh`, run `gh auth login` again, then retry. For git-only clones, re-enter GitHub credentials or a personal access token when prompted.

## Troubleshooting

| Problem | What to try |
|--------|-------------|
| `git` not recognized | Reinstall Git for Windows and open a **new** terminal |
| `gh` not recognized | Use **Option B (git only)**, or reinstall GitHub CLI and open a **new** terminal |
| `gh auth status` fails | Run `gh auth login`, or switch to git-only clone/auth |
| `python` not recognized | Reinstall Python with **Add to PATH**, or use `py` instead of `python` |
| `pip` / install errors | Run: `python -m pip install --upgrade pip` then install `requirements.txt` again |
| App window does not open | Run `python main.py` in the ControlApp folder and read the error text |
| Wrong code / old behavior | Run `git branch` and confirm you are on `support/controlapp`, then `git fetch` + `git pull` |

## Branch note

This branch is **`support/controlapp`**. It is separate from `main` so support fixes can be shared without changing the mainline codebase yet.
