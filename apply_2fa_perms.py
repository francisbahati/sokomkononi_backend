"""
Weka `IsAdminWith2FA` badala ya permission za admin zisizo na 2FA kwenye apps\\.

Inabadilisha mambo matatu:
  1. `permissions.IsAdminUser`  ->  `IsAdminWith2FA`
  2. `from rest_framework.permissions import IsAdminUser, ...`
        ->  `from apps.core.admin_2fa import IsAdminWith2FA as IsAdminUser`
  3. Permission class ya kujitegemea (JINA LOLOTE) ambayo tabia yake ni sawa
     kabisa na ya apps.core.permissions, inabadilishwa kuwa alias yake:
        - inakagua staff tu                -> IsAdminWith2FA
        - inakagua superuser tu            -> IsSuperUser (core, yenye 2FA)
        - kusoma wote, kuandika staff tu   -> IsAdminOrReadOnly (core, yenye 2FA)
     Zenye mantiki tofauti (is_active, role, has_object_permission, staff AU
     superuser, n.k.) HAZIGUSWI — zinaripotiwa ukague kwa mkono.

Kwenye cmd, kutoka folda kuu ya backend (ile yenye `apps\\`):

    python apply_2fa_perms.py            (HAKIBADILISHI — inaonyesha tu)
    python apply_2fa_perms.py --apply    (inaandika mabadiliko)

Kisha kagua kwa `git diff`. Script:
  - inaweka `from apps.core.admin_2fa import IsAdminWith2FA` kabla ya import ya
    kwanza ya faili (baada ya `from __future__` / docstring),
  - inahifadhi line endings za kila faili (CRLF/LF),
  - inakagua kwamba faili bado linakompaili kabla ya kuliandika; likishindwa,
    linaliruka na kukuambia,
  - ni salama kuiendesha tena (faili zilizobadilishwa hazibadilishwi mara mbili).
"""
import ast
import os
import re
import sys

APPLY = "--apply" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
ROOT = args[0] if args else "apps"

SKIP_DIRS = {"migrations", "tests", "__pycache__", ".git", "venv", ".venv", "node_modules"}
SKIP_FILES = {"admin_2fa.py"}
CORE_PERMISSIONS = os.path.join("core", "permissions.py")  # chanzo cha core — hakiguswi
OLD = re.compile(r"\bpermissions\.IsAdminUser\b")
NEW = "IsAdminWith2FA"
IMPORT_LINE = "from apps.core.admin_2fa import IsAdminWith2FA"


def py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if name.endswith(".py") and name not in SKIP_FILES and not full.endswith(CORE_PERMISSIONS):
                yield full


IMPORT_RX = re.compile(r"^from rest_framework\.permissions import ([^()\n]+)$", re.M)
PLAIN_IMPORT_RX = re.compile(r"^from apps\.core\.admin_2fa import IsAdminWith2FA\s*$", re.M)


def convert_drf_import(text):
    def sub(m):
        names = [n.strip() for n in m.group(1).split(",") if n.strip()]
        if "IsAdminUser" not in names:
            return m.group(0)
        rest = [n for n in names if n != "IsAdminUser"]
        out = []
        if rest:
            out.append("from rest_framework.permissions import " + ", ".join(rest))
        out.append("from apps.core.admin_2fa import IsAdminWith2FA as IsAdminUser")
        return "\n".join(out)

    return IMPORT_RX.sub(sub, text)


CORE_IMPORTS = {
    "IsAdminWith2FA": "from apps.core.admin_2fa import IsAdminWith2FA",
    "IsSuperUser2FA": "from apps.core.permissions import IsSuperUser as IsSuperUser2FA",
    "IsAdminOrReadOnly2FA": (
        "from apps.core.permissions import IsAdminOrReadOnly as IsAdminOrReadOnly2FA"
    ),
}


def _classify_permission_class(node):
    """
    Rudisha jina la class ya core (kwenye CORE_IMPORTS) kama tabia ya `node` ni
    sawa kabisa; vinginevyo None. Class lazima iwe na `has_permission` PEKEE.
    """
    methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
    others = [
        n for n in node.body
        if not isinstance(n, ast.FunctionDef)
        and not (isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant))
    ]
    if others or len(methods) != 1 or methods[0].name != "has_permission":
        return None
    fn = methods[0]
    attrs = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    attrs |= {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == "SAFE_METHODS"}
    attrs.discard("user")
    optional = {"is_authenticated"}
    core = attrs - optional
    if core == {"is_staff"}:
        return "IsAdminWith2FA"
    if core == {"is_superuser"}:
        return "IsSuperUser2FA"
    if core == {"is_staff", "SAFE_METHODS", "method"}:
        return "IsAdminOrReadOnly2FA"
    return None


def convert_local_class(text, notes):
    """
    Permission class za kujitegemea zenye tabia sawa na za core -> alias.
    Rudisha (text_mpya, imports_zinazohitajika).
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, []
    lines = text.split("\n")
    needed = []
    for node in reversed(tree.body):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(ast.unparse(b).endswith("BasePermission") for b in node.bases):
            continue
        seg = "\n".join(lines[node.lineno - 1:node.end_lineno])
        if "is_staff" not in seg and "is_superuser" not in seg:
            continue  # si permission ya admin
        target = _classify_permission_class(node)
        if target is None:
            notes.append(
                f"class {node.name} (mstari {node.lineno}) ina mantiki tofauti — "
                "angalia kwa mkono"
            )
            continue
        lines[node.lineno - 1:node.end_lineno] = [
            "# Staff/superuser + 2FA (angalia apps/core/admin_2fa.py)",
            f"{node.name} = {target}",
        ]
        if target not in needed:
            needed.append(target)
    return "\n".join(lines), needed


def needs_plain_import(text):
    if PLAIN_IMPORT_RX.search(text):
        return False
    for line in text.split("\n"):
        if "IsAdminWith2FA" in line and not line.startswith("from apps.core.admin_2fa"):
            return True
    return False


def insert_import(text, import_line=IMPORT_LINE):
    """Weka import_line kabla ya import ya kwanza (baada ya __future__)."""
    if import_line in text:
        return text
    tree = ast.parse(text)
    lines = text.split("\n")
    insert_at = None
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                insert_at = node.end_lineno  # baada ya __future__
                continue
            if insert_at is None:
                insert_at = node.lineno - 1
            break
    if insert_at is None:  # faili halina import yoyote
        insert_at = 0
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(
            getattr(tree.body[0], "value", None), ast.Constant
        ):
            insert_at = tree.body[0].end_lineno  # baada ya docstring
    lines.insert(insert_at, import_line)
    return "\n".join(lines)


def main():
    if not os.path.isdir(ROOT):
        print(f"Folda '{ROOT}' haipo. Endesha kutoka folda kuu ya backend.")
        sys.exit(1)

    changed, skipped = [], []
    for path in py_files(ROOT):
        with open(path, "rb") as fh:
            raw = fh.read().decode("utf-8", errors="replace")
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        notes = []
        count = len(OLD.findall(text))
        new_text = OLD.sub(NEW, text)
        new_text = convert_drf_import(new_text)
        new_text, extra_imports = convert_local_class(new_text, notes)
        if new_text == text:
            for n in notes:
                skipped.append((path, n))
            continue
        try:
            for name in extra_imports:
                if name != "IsAdminWith2FA":
                    new_text = insert_import(new_text, CORE_IMPORTS[name])
            if needs_plain_import(new_text):
                new_text = insert_import(new_text)
            compile(new_text, path, "exec")
        except SyntaxError as exc:
            skipped.append((path, f"haikompaili baada ya mabadiliko: {exc}"))
            continue
        for n in notes:
            skipped.append((path, n))
        changed.append((path, count))
        if APPLY:
            out = new_text.replace("\n", "\r\n") if crlf else new_text
            with open(path, "wb") as fh:
                fh.write(out.encode("utf-8"))

    mode = "IMEANDIKWA" if APPLY else "ONYESHO TU (ongeza --apply kuandika)"
    print(f"== {mode} ==")
    for path, n in changed:
        print(f"  {path}: {n or 'import/class'} mabadiliko")
    for path, why in skipped:
        print(f"  RUKA {path}: {why}")
    print(f"\nFaili: {len(changed)} | zilizoruka: {len(skipped)}")
    if APPLY and changed:
        print("Sasa endesha:  git diff   kisha:  python scan_admin_perms.py")


if __name__ == "__main__":
    main()
