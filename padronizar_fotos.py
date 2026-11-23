#!/usr/bin/env python3
"""Deixa todas as fotos com o mesmo tamanho (quadrado, JPG).

Uso:
  python3 padronizar_fotos.py [pasta_origem] [pasta_destino] [--tamanho 400]

Padrão: fotos_originais -> fotos_processadas. Mantém o nome do arquivo.
Corta no centro (um pouco acima, para não cortar rostos) e corrige a rotação.
Requer: pip install pillow  (opcional: pillow-heif para .heic)
"""
import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Instale o Pillow primeiro:  pip install pillow")
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("origem", nargs="?", default="fotos_originais")
    ap.add_argument("destino", nargs="?", default="fotos_processadas")
    ap.add_argument("--tamanho", type=int, default=400)
    a = ap.parse_args()

    origem, destino = Path(a.origem), Path(a.destino)
    if not origem.is_dir():
        sys.exit(f"Pasta não encontrada: {origem}")
    destino.mkdir(parents=True, exist_ok=True)

    n = 0
    for p in sorted(origem.iterdir()):
        if p.suffix.lower() not in EXT:
            continue
        try:
            img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            img = ImageOps.fit(img, (a.tamanho, a.tamanho), Image.LANCZOS, centering=(0.5, 0.4))
            out = destino / f"{p.stem}.jpg"
            img.save(out, "JPEG", quality=85, optimize=True)
            print(f"OK    {p.name} -> {out.name} ({a.tamanho}x{a.tamanho})")
            n += 1
        except Exception as e:
            print(f"ERRO  {p.name}: {e}")
    print(f"\n{n} foto(s) em '{destino}'.")


if __name__ == "__main__":
    main()
