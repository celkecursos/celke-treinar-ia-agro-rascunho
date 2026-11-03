"""Extrai os arquivos dos prompts numa pasta temporária e compara com o projeto (mesmas trocas do gerador)."""
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gerar_prompts import FILES, REPO, content  # noqa: E402

PROMPTS = REPO / "docs" / "prompts-iniciais"
DEST = Path(tempfile.mkdtemp())
ORDER = ["f00-01-preparacao-e-modelo.md", "f01-01-estrutura-e-docker.md", "f02-01-backend.md",
         "f03-01-frontend-kole.md", "f04-01-fine-tuning.md", "f06-01-documentacao.md"]
ok = bad = 0
seen = set()
for name in ORDER:
    text = (PROMPTS / name).read_text(encoding="utf-8")
    for path, body in re.findall(r"^`([^`\n]+)`:\n\n`{6}[a-z]*\n(.*?)^`{6}$", text, re.M | re.S):
        seen.add(path)
        target = DEST / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8", newline="\n")
    for path in re.findall(r"^- `([^`\n]+)`$", text.split("arquivos **vazios**:")[1].split("\n\n")[1], re.M) if "arquivos **vazios**:" in text else []:
        seen.add(path)
        target = DEST / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

files = [f for f in FILES if f != "frontend/package-lock.json"]
for f in files:
    original = content(f)
    got = (DEST / f).read_text(encoding="utf-8") if (DEST / f).exists() else None
    if got == original or (got is not None and got.rstrip("\n") == original.rstrip("\n")):
        ok += 1
    else:
        bad += 1
        print("DIFERENTE", f, None if got is None else (len(got), len(original)))
print("iguais", ok, "diferentes", bad, "sobrando", sorted(seen - set(files)))
sys.exit(1 if bad or seen - set(files) else 0)
