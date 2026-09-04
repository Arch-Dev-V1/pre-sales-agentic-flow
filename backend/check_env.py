"""
Diagnose ANTHROPIC_API_KEY problems without ever printing the key.

Run it from the backend/ directory with the project's venv:

    python check_env.py

Written after a 401 on a second machine that had a working .env: the
usual causes are all invisible from the outside (a shadowing OS
variable, Notepad saving .env.txt, a UTF-8 BOM, an unreplaced
placeholder), and they produce different errors that look identical.
"""

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
ENV = HERE / ".env"
PROBLEMS = []


def check(label: str, ok: bool, detail: str = "", fatal: str = "") -> bool:
    print(f"  [{'OK ' if ok else 'BAD'}] {label}{f' — {detail}' if detail else ''}")
    if not ok and fatal:
        PROBLEMS.append(fatal)
    return ok


print("\nANTHROPIC_API_KEY diagnostic\n" + "=" * 46)

# 1. Is the key already in the OS environment? load_dotenv() does NOT
#    override an existing variable, so a stale one silently wins.
preexisting = os.environ.get("ANTHROPIC_API_KEY")
check(
    "no shadowing OS environment variable",
    preexisting is None,
    "" if preexisting is None else f"one is set ({len(preexisting)} chars) and would win over .env",
    "Remove the machine-level ANTHROPIC_API_KEY (setx ANTHROPIC_API_KEY \"\" then reopen the "
    "terminal), or keep it and make sure it holds a valid key.",
)

# 2. Does the file exist, and is it named correctly?
if not check("backend/.env exists", ENV.is_file(), str(ENV),
             "Create backend/.env — copy .env.example and put your real key in it."):
    strays = [p.name for p in HERE.glob(".env*") if p.name not in (".env", ".env.example")]
    if strays:
        print(f"        found instead: {strays}  <- Notepad appends .txt unless you pick "
              f'"All Files" in the Save-as-type dropdown')
    print("\n" + "\n".join(f"  -> {p}" for p in PROBLEMS) + "\n")
    sys.exit(1)

# 3. BOM: Notepad's "UTF-8 with BOM" turns the first key name into
#    "﻿ANTHROPIC_API_KEY", so the real name is never set.
raw = ENV.read_bytes()
check("no UTF-8 BOM at the start of .env", not raw.startswith(b"\xef\xbb\xbf"),
      "" if not raw.startswith(b"\xef\xbb\xbf") else "first line's key name is corrupted",
      "Re-save backend/.env as UTF-8 without BOM (Notepad: Save as -> Encoding: UTF-8).")

# 4. Read the value the way python-dotenv will.
value = None
for line in raw.decode("utf-8-sig", errors="replace").splitlines():
    line = line.strip()
    if line.startswith("#") or "=" not in line:
        continue
    name, _, val = line.partition("=")
    if name.strip() == "ANTHROPIC_API_KEY":
        value = val.strip().strip('"').strip("'")

if not check("ANTHROPIC_API_KEY line present in .env", value is not None, "",
             "Add a line: ANTHROPIC_API_KEY=sk-ant-..."):
    print("\n" + "\n".join(f"  -> {p}" for p in PROBLEMS) + "\n")
    sys.exit(1)

check("placeholder was replaced", value != "sk-ant-...", "" if value != "sk-ant-..." else
      "still the literal placeholder from .env.example",
      "Replace sk-ant-... in backend/.env with your real key.")
check("starts with sk-ant-", value.startswith("sk-ant-"), f"starts {value[:7]!r}",
      "The value doesn't look like an Anthropic key — check you pasted the whole thing.")
check("plausible length", len(value) > 90, f"{len(value)} chars",
      "The key looks truncated — copy it again, it should be ~108 characters.")
check("no stray whitespace inside", not any(c.isspace() for c in value), "",
      "The key contains a space or line break — paste it as a single unbroken line.")

# 5. What will the app actually use, after load_dotenv()?
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ENV)
effective = os.environ.get("ANTHROPIC_API_KEY", "")
source = "the OS environment (NOT your .env)" if preexisting else "backend/.env"
print(f"\n  The app will use the key from: {source}  ({len(effective)} chars)")

if PROBLEMS:
    print("\n  Fix these:\n" + "\n".join(f"   -> {p}" for p in PROBLEMS) + "\n")
    sys.exit(1)

# 6. Free, non-billed call that proves the key is accepted.
print("\n  Verifying against the API (free, consumes no tokens)...")
try:
    import anthropic

    models = anthropic.Anthropic().models.list(limit=5).data
    print(f"  [OK ] key accepted — {len(models)} models visible\n")
except Exception as e:  # noqa: BLE001
    print(f"  [BAD] {type(e).__name__}: {str(e)[:160]}\n")
    sys.exit(1)
