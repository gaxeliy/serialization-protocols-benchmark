"""Auto-generate generated/benchmark/__init__.py after flatc --python.

Iterates over the generated Python files and writes proper imports
so that the benchmark package is usable directly.
"""

import os
from pathlib import Path


GENERATED_DIR = Path(__file__).resolve().parent / "generated" / "benchmark"


def main():
    py_files = sorted(f for f in os.listdir(GENERATED_DIR) if f.endswith(".py") and f != "__init__.py")
    lines = []
    for f in py_files:
        module = f[:-3]
        # Check if the module defines a class with the same name
        filepath = GENERATED_DIR / f
        content = filepath.read_text()
        # Import the class
        if f"class {module}(" in content:
            lines.append(f"from .{module} import {module}")

        # Import builder functions (Start/End/Add*)
        # Look for top-level function definitions matching the module namespace
        for func_name in extract_functions(content, module):
            lines.append(f"from .{module} import {func_name}")

    init_path = GENERATED_DIR / "__init__.py"
    init_path.write_text("\n".join(lines) + "\n")
    print(f"Generated {init_path} ({len(lines)} imports)")


def extract_functions(content: str, module: str) -> list[str]:
    """Return only *prefixed* builder-function names from a flatbuffers module.

    Each module has both short aliases (Start, End, AddFoo) and long names
    (SmallMessageStart, …).  Only the long names are safe to export because
    short names collide across modules.
    """
    import re
    funcs = set()
    for match in re.finditer(r"^def (\w+)\(.*", content, re.MULTILINE):
        name = match.group(1)
        # Skip class-name ctor and short un-prefixed aliases
        if name == module:
            continue
        if name.startswith(module):
            funcs.add(name)
    return sorted(funcs)


if __name__ == "__main__":
    main()
