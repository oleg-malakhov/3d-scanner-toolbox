# ControlApp — Windows Quick Start (support branch)

Use this guide if you need to run **ControlApp** from the `support/controlapp` branch on Windows.

## Prerequisites

1. **Git for Windows** — [https://git-scm.com/download/win](https://git-scm.com/download/win)  
   During install, keep the option that adds Git to PATH.

2. **Python 3.8 or later** — [https://www.python.org/downloads/](https://www.python.org/downloads/)  
   On the installer first screen, check **Add python.exe to PATH**.

3. USB connection from the PC to the Arduino / CNC controller (after hardware is assembled).

Verify in **Command Prompt** or **PowerShell**:

```bat
git --version
python --version
```

You should see Git and Python 3.8+ versions. If `python` is not found, try `py --version` instead.

## 1. Clone the repository

Open **Command Prompt** or **PowerShell**, then:

```bat
cd %USERPROFILE%\Documents
git clone https://github.com/oleg-malakhov/3d-scanner-toolbox.git
cd 3d-scanner-toolbox
```

If you already cloned the repo earlier, skip `git clone` and just `cd` into the existing folder.

## 2. Check out the support branch

```bat
git fetch origin
git checkout support/controlapp
git pull
```

Confirm you are on the right branch:

```bat
git branch
```

You should see `* support/controlapp`.

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

## Updating later

When fixes are pushed to this branch, update with:

```bat
cd %USERPROFILE%\Documents\3d-scanner-toolbox
git checkout support/controlapp
git pull
cd OpenScanTurntable\ControlApp
run.bat
```

## Troubleshooting

| Problem | What to try |
|--------|-------------|
| `git` not recognized | Reinstall Git for Windows and open a **new** terminal |
| `python` not recognized | Reinstall Python with **Add to PATH**, or use `py` instead of `python` |
| `pip` / install errors | Run: `python -m pip install --upgrade pip` then install `requirements.txt` again |
| App window does not open | Run `python main.py` in the ControlApp folder and read the error text |
| Wrong code / old behavior | Run `git branch` and confirm you are on `support/controlapp`, then `git pull` |

## Branch note

This branch is **`support/controlapp`**. It is separate from `main` so support fixes can be shared without changing the mainline codebase yet.
