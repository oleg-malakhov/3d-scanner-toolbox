# ControlApp — Windows Quick Start (support branch)

Use this guide if you need to run **ControlApp** from the `support/controlapp` branch on Windows.

## Prerequisites

1. **Git for Windows** — [https://git-scm.com/download/win](https://git-scm.com/download/win)  
   During install, keep the option that adds Git to PATH.

2. **GitHub CLI (`gh`)** — already installed. Confirm with `gh --version`.  
   If you are not logged in yet: `gh auth login` (follow the prompts; choose HTTPS).

3. **Python 3.8 or later** — [https://www.python.org/downloads/](https://www.python.org/downloads/)  
   On the installer first screen, check **Add python.exe to PATH**.

4. USB connection from the PC to the Arduino / CNC controller (after hardware is assembled).

Verify in **Command Prompt** or **PowerShell**:

```bat
git --version
gh --version
python --version
gh auth status
```

You should see Git, `gh`, and Python 3.8+ versions, and a successful GitHub login. If `python` is not found, try `py --version` instead.

## 1. Clone the repository

You will be given a repository name in the form `owner/3d-scanner-toolbox`. Open **Command Prompt** or **PowerShell**, then:

```bat
cd %USERPROFILE%\Documents
gh repo clone owner/3d-scanner-toolbox -- -b support/controlapp
cd 3d-scanner-toolbox
```

Replace `owner/3d-scanner-toolbox` with the exact repo name you were given.  
The `-- -b support/controlapp` part clones and checks out the support branch in one step.

If you already cloned the repo earlier, skip cloning and just `cd` into the existing folder, then continue with section 2.

### Alternative without branch flag

```bat
cd %USERPROFILE%\Documents
gh repo clone owner/3d-scanner-toolbox
cd 3d-scanner-toolbox
git fetch origin
git checkout support/controlapp
```

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

When you are told that fixes were pushed to `support/controlapp`, pull them and restart the app:

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
- If `git pull` fails with an auth error, run `gh auth login` again, then retry.

## Troubleshooting

| Problem | What to try |
|--------|-------------|
| `git` not recognized | Reinstall Git for Windows and open a **new** terminal |
| `gh` not recognized | Reinstall GitHub CLI and open a **new** terminal |
| `gh auth status` fails | Run `gh auth login` and complete the browser login |
| `python` not recognized | Reinstall Python with **Add to PATH**, or use `py` instead of `python` |
| `pip` / install errors | Run: `python -m pip install --upgrade pip` then install `requirements.txt` again |
| App window does not open | Run `python main.py` in the ControlApp folder and read the error text |
| Wrong code / old behavior | Run `git branch` and confirm you are on `support/controlapp`, then `git fetch` + `git pull` |

## Branch note

This branch is **`support/controlapp`**. It is separate from `main` so support fixes can be shared without changing the mainline codebase yet.
