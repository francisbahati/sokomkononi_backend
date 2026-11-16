"""
Tafuta endpoints za admin ambazo bado hazijalindwa na 2FA.

Endesha kutoka folda kuu ya backend (ile yenye `apps\\`), kwenye cmd:

    python scan_admin_perms.py
    python scan_admin_perms.py apps          (folda nyingine ukipenda)

Haibadilishi faili lolote — inaorodhesha tu.
"""
import ast
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "apps"

SKIP_DIRS = {"migrations", "tests", "__pycache__", "node_modules", ".git", "venv", ".venv"}
SKIP_FILES = {"admin_2fa.py", "admin.py"}  # admin.py = Django admin (angalia maelezo)

CHECKS = [
    (
        "BADILISHA",
        "DRF permissions.IsAdminUser → tumia IsAdminWith2FA",
        re.compile(r"\bpermissions\.IsAdminUser\b"),
    ),
    (
        "BADILISHA",
        "import ya IsAdminUser kutoka rest_framework.permissions",
        re.compile(r"from\s+rest_framework\.permissions\s+import[^\n]*\bIsAdminUser\b"),
    ),
    (
        "BADILISHA",
        "IsAdminUser ya kujitegemea (badala yake: IsAdminUser = IsAdminWith2FA)",
        re.compile(r"^\s*class\s+IsAdminUser\s*\((?!\s*IsAdminWith2FA)"),
    ),
    (
        "KAGUA",
        "ukaguzi wa mkono wa is_staff / is_superuser — je, view ina permission ya 2FA, "
        "au ongeza require_admin_2fa(request)?",
        re.compile(r"\bis_staff\b|\bis_superuser\b"),
    ),
]

OK_PATTERNS = [
    re.compile(r"\bIsAdminWith2FA\b"),
    re.compile(r"from\s+apps\.core\.permissions\s+import[^\n]*\b(IsAdminUser|IsSuperUser|IsAdminOrReadOnly)\b"),
]


def py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py") and name not in SKIP_FILES:
                yield os.path.join(dirpath, name)


def local_permission_classes(text):
    """Permission class za kujitegemea (jina lolote) zinazokagua is_staff/is_superuser."""
    out = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    lines = text.split("\n")
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(ast.unparse(b).endswith("BasePermission") for b in node.bases):
            continue
        seg = "\n".join(lines[node.lineno - 1:node.end_lineno])
        if ("is_staff" in seg or "is_superuser" in seg) and "admin_2fa" not in seg and "IsAdminWith2FA" not in seg:
            kind = "superuser" if "is_superuser" in seg else "staff"
            out.append((node.lineno, node.name, kind))
    return out


def main():
    if not os.path.isdir(ROOT):
        print(f"Folda '{ROOT}' haipo. Endesha kutoka folda kuu ya backend.")
        sys.exit(1)

    findings = {"BADILISHA": {}, "KAGUA": {}}
    local_classes = {}
    covered = 0
    for path in py_files(ROOT):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        text = "\n".join(lines)
        if any(p.search(text) for p in OK_PATTERNS):
            covered += 1
        found = local_permission_classes(text)
        if found and not path.endswith(os.path.join("core", "permissions.py")):
            local_classes[path] = found
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith("#"):
                continue
            for level, label, rx in CHECKS:
                if rx.search(line):
                    findings[level].setdefault(path, []).append((i, label, line.strip()))

    print("=" * 70)
    print("A) LAZIMA UBADILISHE (zinapita bila 2FA)")
    print("=" * 70)
    if not findings["BADILISHA"]:
        print("  Hakuna. Vizuri.")
    for path, items in sorted(findings["BADILISHA"].items()):
        print(f"\n{path}")
        for i, label, line in items:
            print(f"  {i:>5}: {line[:90]}")
            print(f"         ↳ {label}")

    print("\n" + "=" * 70)
    print("A2) PERMISSION CLASS ZA KUJITEGEMEA (jina lolote) — hazikagui 2FA")
    print("    Kuandika (POST/PUT/PATCH/DELETE) kunalindwa na Admin2FA guard ya")
    print("    jumla (apps/core/auth.py); KUSOMA bado hakulindwi na class hizi.")
    print("    Njia bora: badilisha class hizi ziitumie IsAdminWith2FA / apps.core.permissions.")
    print("=" * 70)
    if not local_classes:
        print("  Hakuna.")
    for path, items in sorted(local_classes.items()):
        print(f"\n{path}")
        for lineno, name, kind in items:
            print(f"  {lineno:>5}: class {name}  (inakagua {kind})")

    print("\n" + "=" * 70)
    print("B) KAGUA KWA MKONO (is_staff / is_superuser)")
    print("=" * 70)
    if not findings["KAGUA"]:
        print("  Hakuna.")
    for path, items in sorted(findings["KAGUA"].items()):
        print(f"\n{path}  ({len(items)})")
        for i, _label, line in items[:6]:
            print(f"  {i:>5}: {line[:90]}")
        if len(items) > 6:
            print(f"         ... na {len(items) - 6} zaidi")

    n_a = sum(len(v) for v in findings["BADILISHA"].values())
    n_b = sum(len(v) for v in findings["KAGUA"].values())
    print("\n" + "-" * 70)
    print(f"Faili zinazotumia permission ya 2FA: {covered}")
    print(f"A) kubadilisha: {n_a} mistari kwenye {len(findings['BADILISHA'])} faili")
    print(f"A2) class za kujitegemea: {sum(len(v) for v in local_classes.values())} kwenye {len(local_classes)} faili")
    print(f"B) kukagua:     {n_b} mistari kwenye {len(findings['KAGUA'])} faili")


if __name__ == "__main__":
    main()
