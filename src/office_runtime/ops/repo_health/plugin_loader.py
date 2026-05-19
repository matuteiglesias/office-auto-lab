

def _chunk_list(xs, n):
    """Yield successive n-sized chunks from list xs."""
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


# utils for A1 ranges

def col_idx_to_letter(idx: int) -> str:
    """1-based column index -> A, B, ..., Z, AA, AB, ..."""
    letters = []
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters.append(chr(ord('A') + rem))
    return ''.join(reversed(letters))


def row_to_dict(header, row):
    return { h: row[i] if i < len(row) else "" for i,h in enumerate(header) }


import sys, os, importlib, traceback, pkgutil
from typing import Dict, Any

# plugin loader (plugins folder must exist, each plugin module should define a class subclassing plugins.base.BasePlugin)
def load_plugins_from_folder(folder="src/office_runtime/ops/repo_health/plugins") -> Dict[str, Any]:
    plugins = {}
    # ensure package importable
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    # iterate modules in folder
    if not os.path.isdir(folder):
        print(f"plugins folder '{folder}' not found")
        return plugins
    for finder, name, ispkg in pkgutil.iter_modules([folder]):
        if name.endswith("_plugin"):
            mod_name = f"office_runtime.ops.office_runtime.ops.office_runtime.ops.repo_health.plugins.{name}"
            try:
                mod = importlib.import_module(mod_name)
                print(f"Tried import {mod_name}")
            except Exception:
                print(f"failed import {mod_name}\n{traceback.format_exc()}")
                continue
            # find plugin classes
            for attr in dir(mod):
                obj = getattr(mod, attr)
                try:
                    from office_runtime.ops.office_runtime.ops.office_runtime.ops.repo_health.plugins.base import BasePlugin
                    if isinstance(obj, type) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                        inst = obj()
                        plugins[inst.name] = inst
                except Exception:
                    continue


    return plugins

