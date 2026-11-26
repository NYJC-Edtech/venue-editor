#!/usr/bin/env python3
"""Extract the editor template's <script> body, syntax-check it with node,
and rebuild editor.html from the current metadata.json (same embed step as
convert_inkscape.py, without re-running the SVG conversion)."""
import json, re, subprocess, sys, tempfile, os

TPL = "editor_template.html"
OUT = "editor.html"

tpl = open(TPL, encoding="utf-8").read()
m = re.search(r"<script>\n(.*)\n</script>", tpl, re.DOTALL)
if not m:
    sys.exit("no <script> block found")
js = m.group(1)
fd, path = tempfile.mkstemp(suffix=".js", dir=".")   # workspace path: Windows node can't see /tmp
try:
    os.write(fd, js.encode("utf-8"))
    os.close(fd)
    r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr)
        sys.exit("JS SYNTAX ERROR")
    print("JS syntax OK")
finally:
    os.unlink(path)

meta = json.load(open("metadata.json", encoding="utf-8"))
compact = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
assert "/*__DATA__*/ null" in tpl, "template lacks the /*__DATA__*/ placeholder"
open(OUT, "w", encoding="utf-8", newline="\n").write(tpl.replace("/*__DATA__*/ null", compact))
print(f"editor built: {OUT}")
