# fix_views.py
# Sasisha indentation ya apps/listings/views.py
# Tumia: python fix_views.py

import re
import ast
import shutil
from datetime import datetime


PATH = "apps/listings/views.py"
BACKUP = f"apps/listings/views.py.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def find_method_block(lines, method_name):
    """
    Tafuta block ya method (kutoka `def method_name` au `@action` iliyo
    juu yake, hadi mstari wa mwisho wa method).

    Returns: (start_index, end_index) — inclusive start, exclusive end.
    """
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^\s*def {method_name}\(", line):
            start = i
            break

    if start is None:
        return None, None

    # Rudi nyuma ili kukamata decorators (@action, n.k.)
    while start > 0 and lines[start - 1].strip().startswith("@"):
        start -= 1

    # Tafuta mwisho — mstari wa kwanza baada ya method ambao
    # hauna indentation (au ni mstari tupu mwishoni)
    end = start + 1
    while end < len(lines):
        line = lines[end]
        stripped = line.rstrip("\n")

        # Mstari tupu — endelea
        if not stripped.strip():
            end += 1
            continue

        # Comment ya top-level (kama `# ====`) — endelea
        if stripped.lstrip().startswith("#"):
            end += 1
            continue

        # Kama mstari hauna indentation (au decorator @), ni mwisho
        if not stripped.startswith((" ", "\t")):
            break

        end += 1

    return start, end


def normalize_block(lines, start, end):
    """
    Rekebisha indentation ya block nzima:
    - Mstari wa `@action(` na `def xxx(` → spaces 4
    - `detail=`, `methods=`, n.k. → spaces 8
    - `)` ya mwisho → spaces 4
    """
    new_block = []
    for i in range(start, end):
        line = lines[i]
        stripped = line.lstrip()

        if not stripped.strip():
            new_block.append(line)
            continue

        # Decorator `@action(` au `@anything`
        if stripped.startswith("@"):
            new_block.append("    " + stripped)
            continue

        # `def method_name(...)`
        if stripped.startswith("def "):
            new_block.append("    " + stripped)
            continue

        # `)` ya decorator au `],` au `)`
        if stripped in (")", "],", "],", "),"): 
            new_block.append("    " + stripped)
            continue

        # Arguments za decorator (detail=, methods=, n.k.)
        if stripped.startswith(("detail=", "methods=", "url_path=", "permission_classes=")):
            new_block.append("        " + stripped)
            continue

        # Body ya method — preserve kama ilivyo, lakini hakikisha ina
        # angalau spaces 8
        current_indent = len(line) - len(stripped)
        if current_indent < 8:
            new_block.append("        " + stripped)
        else:
            new_block.append(line)

    return new_block


def fix_similar(lines):
    """Rekebisha block ya `similar()` method."""
    start, end = find_method_block(lines, "similar")
    if start is None:
        print("  KOSA: `similar()` method haipatikani.")
        return lines

    print(f"  `similar()` ipo mistari {start + 1}-{end}")

    # Rebuild block — rudisha kwa indentation sahihi
    # Hatua 1: Toa mistari yote na uipange upya
    block = lines[start:end]
    
    # Chukua body ya method kama ilivyo (bila decorator na def)
    # Kisha rudisha decorator + def kwa indentation sahihi
    new_block = []
    
    i = 0
    # Decorator
    while i < len(block) and block[i].strip().startswith("@"):
        stripped = block[i].strip()
        if stripped.endswith("("):
            new_block.append("    " + stripped)
            i += 1
            # Arguments za decorator
            while i < len(block) and not block[i].strip().startswith(")"):
                new_block.append("        " + block[i].strip())
                i += 1
            if i < len(block):
                new_block.append("    " + block[i].strip())
                i += 1
        else:
            new_block.append("    " + stripped)
            i += 1
    
    # Def line
    while i < len(block):
        line = block[i]
        stripped = line.strip()
        if not stripped:
            new_block.append("")
            i += 1
            continue
        if stripped.startswith("def "):
            new_block.append("    " + stripped)
            i += 1
            break
        i += 1
    
    # Body — chukua kama ilivyo, lakini kama mistari mingine
    # ina indentation isiyo ya kawaida, isahihishe
    body_lines = block[i:]
    body_lines = [l.rstrip() for l in body_lines]  # ondoa trailing whitespace
    new_block.extend(body_lines)
    
    return lines[:start] + new_block + lines[end:]


def main():
    print(f"Kusoma {PATH}...")
    with open(PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"  Mistari: {len(lines)}")

    # Backup
    print(f"Kutengeneza backup: {BACKUP}")
    shutil.copy(PATH, BACKUP)

    # Rekebisha `similar()`
    print("\nKurekebisha `similar()`...")
    lines = fix_similar(lines)

    # Andika
    with open(PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Thibitisha syntax
    print("\nKuthibitisha syntax...")
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        print("  OK — syntax ni sahihi")
    except SyntaxError as e:
        print(f"  KOSA la syntax: {e}")
        print(f"  Mstari {e.lineno}: {e.text}")
        print(f"\n  Backup ipo kwenye: {BACKUP}")
        print(f"  Rejesha kwa: copy {BACKUP} {PATH}")
        return 1

    print(f"\nImekamilika. Angalia mabadiliko:")
    print(f"  git diff {PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())