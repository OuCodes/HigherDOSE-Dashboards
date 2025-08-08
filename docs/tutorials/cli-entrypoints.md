# GrowthKit — CLI Entry-Points Tutorial

> Last updated: 2025-07-26

This short guide explains **why** we use *console-script entry points* and shows **exactly** how to add, rename, or remove them. Follow these steps whenever you need a new command-line interface (CLI) for a module, or when you modify existing ones.

---

## 1 What’s an *Entry Point*?

A *console-script entry point* is a small, automatically-generated wrapper that makes a Python function available as a shell command **anywhere in your virtual-environment**.  For example, the entry point:

```toml
[project.scripts]
gk-weekly = "growthkit.reports.weekly:main"
```
creates an executable called `gk-weekly` that imports `growthkit.reports.weekly` and calls its `main()` function.

---

## 2 Declaring Entry Points

1. Open `pyproject.toml`.
2. Scroll (or add) to the **`[project.scripts]`** table.
3. Add lines in the form:
   ```toml
   <command-name> = "<module-path>:<callable>"
   ```

### Example – current project setup

```toml
[project.scripts]
gk-weekly = "growthkit.reports.weekly:main"
gk-h1     = "growthkit.reports.h1:main"
# Async functions → wrap in a sync helper
gk-slack  = "growthkit.connectors.slack.slack_fetcher:run_main"
gk-email  = "growthkit.connectors.mail.gmail_sync:main"
```

**Naming convention**

* Use the short `gk-*` prefix for user-facing commands.

---

## 3 Installing / Rebuilding the Package

After **every** change to `pyproject.toml` you must reinstall the project so that `pip` regenerates the wrapper scripts.

```bash
# 1) Activate the development virtual-env (create if missing)
$ python3 -m venv venv        # one-time setup
$ source venv/bin/activate

# 2) Install in *editable* (-e) mode → instant rebuilds
(venv) $ pip install -e .
```

Why *editable*? Because it symlinks your source tree into the venv, so changes are picked up without re-installation (except for entry-points and dependency list updates).

> 🛈  **PEP 668 / Homebrew Python**: If you’re on macOS and see the “externally-managed-environment” error, you’re using the system Python. Always install & work inside a venv. (See Quick Start in `README.md`.)

---

## 4 Verifying Everything Works

With the venv active:

```bash
(venv) $ which gk-weekly   # should print path inside ./venv/bin/
(venv) $ gk-weekly --help   # or run the command
```

For async modules (`hd-slack`) we expose a synchronous wrapper function like `run_main()` that simply does `asyncio.run(main())`.  Make sure the entry-point targets **that** wrapper, not the raw `async def main()`.

---

## 5 Common Tasks

### Add a new command
1. Create a `main()` (or `run()`/`cli()`) function in the relevant module.
2. Add a line in `[project.scripts]`.
3. `pip install -e .` again.

### Rename a command
1. Change the key in `[project.scripts]`.
2. Re-install (`pip install -e .`).
3. Optionally, delete the old wrapper:
   ```bash
   (venv) $ rm $(dirname $(which old-command))/old-command
   ```

### Remove a command
1. Delete the line from `[project.scripts]`.
2. Re-install (`pip install -e .`).

### Update dependencies only
If you **didn’t** touch `[project.scripts]`, a normal `pip install -e .` will pick up new deps without rewriting entry points.

---

## 6 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `command not found` | venv not active / not re-installed | `source venv/bin/activate && pip install -e .` |
| Wrapper runs old code | Forgot to reinstall after editing scripts table | `pip install -e .` |
| “externally-managed-environment” error | Using system Python (PEP 668) | Create & activate a venv first |
| Async `RuntimeWarning: coroutine was never awaited` | Entry-point points at async `main` | Point at a synchronous wrapper (e.g. `run_main`) |

---

## 7 Reference Links

* [PEP 621] – Standardising project metadata in `pyproject.toml`
* [Setuptools – Entry Points](https://setuptools.pypa.io/en/stable/userguide/entry_point.html)
* [Packaging – Command Line Interfaces](https://packaging.python.org/en/latest/tutorials/creating-and-discovering/#creating-command-line-tools)


---

Happy hacking!  If anything in this document is unclear or becomes outdated, **please update it immediately**—future developers (and AI assistants) will thank you. 