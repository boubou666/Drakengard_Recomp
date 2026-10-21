"""Install recompiled output and the Drakengard override module into the PS2Recomp runner.

usage: python scripts/sync_runner.py [generated_dir]   (default recomp/output_ghidra)

Copies only files whose contents changed (keeps ninja rebuilds small), removes runner sources that are
no longer generated, and installs runtime/zz_drakengard_overrides.cpp next to them.
"""
import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATED = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else os.path.join("recomp", "output_ghidra"))
RUNTIME = os.path.join(ROOT, "PS2Recomp", "ps2xRuntime")
RUNNER = os.path.join(RUNTIME, "src", "runner")
OVERRIDE = os.path.join(ROOT, "runtime", "zz_drakengard_overrides.cpp")


def copy_if_changed(source, destination):
    if os.path.exists(destination) and filecmp.cmp(source, destination, shallow=False):
        return False
    shutil.copy2(source, destination)
    return True


changed = 0
generated = set(os.listdir(GENERATED))
for name in generated:
    destination = os.path.join(RUNTIME, "include" if name.endswith(".h") else os.path.join("src", "runner"), name)
    changed += copy_if_changed(os.path.join(GENERATED, name), destination)
changed += copy_if_changed(OVERRIDE, os.path.join(RUNNER, os.path.basename(OVERRIDE)))

removed = 0
keep = generated | {os.path.basename(OVERRIDE)}
for name in os.listdir(RUNNER):
    if name.endswith(".cpp") and name not in keep:
        os.remove(os.path.join(RUNNER, name))
        removed += 1

print(f"changed {changed}, removed {removed}")
