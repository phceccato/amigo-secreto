#!/usr/bin/env python3
"""Prepara as fotos e o participantes.json para publicar junto do reveal.html.

Uso:
  python3 preparar_fotos.py participantes.csv fotos_originais [--saida publicar]

Nomeie cada foto com o nome do participante, igual ao do CSV (acentos e
maiúsculas não importam): "Ana.jpg", "Maria Clara.png", "joao.jpeg".
Cada foto vira um quadrado de 400x400 (leve para abrir no celular).
O participantes.json gerado tem SÓ nome e foto (sem telefone, sem sorteio).
Requer: pip install pillow  (opcional: pillow-heif para fotos .heic do iPhone)
"""
import argparse
import csv
import json
import re
import shutil
import sys
import unicodedata
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

TAM = 400
EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def slug(txt: str) -> str:
    s = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("pasta_fotos")
    ap.add_argument("--saida", default="publicar")
    ap.add_argument("--base", help="endereço onde a pasta será publicada, ex.: "
                    "https://nome-do-site.netlify.app/ (ajusta a prévia do link no WhatsApp)")
    a = ap.parse_args()
    if a.base and not re.match(r"^https://[^/\s]+/", a.base.rstrip("/") + "/"):
        sys.exit("--base precisa começar com https:// (ex.: https://nome-do-site.netlify.app/)")

    with open(a.csv, newline="", encoding="utf-8-sig") as f:
        nomes = [(l.get("nome") or "").strip() for l in csv.DictReader(f)]
    nomes = [n for n in nomes if n]
    if not nomes:
        sys.exit("Nenhum nome encontrado no CSV (coluna 'nome').")

    originais = {}
    for p in Path(a.pasta_fotos).iterdir():
        if p.suffix.lower() in EXT:
            originais[slug(p.stem)] = p

    saida = Path(a.saida)
    (saida / "fotos").mkdir(parents=True, exist_ok=True)

    lista, usados, sem_foto = [], set(), []
    for i, nome in enumerate(nomes, 1):
        chave = slug(nome)
        arq = chave if chave and chave not in usados else f"pessoa-{i}"
        usados.add(arq)
        origem = originais.pop(chave, None)
        foto = None
        if origem:
            try:
                img = ImageOps.exif_transpose(Image.open(origem)).convert("RGB")
                img = ImageOps.fit(img, (TAM, TAM), Image.LANCZOS, centering=(0.5, 0.4))
                destino = saida / "fotos" / f"{arq}.jpg"
                img.save(destino, "JPEG", quality=82, optimize=True)
                foto = f"fotos/{arq}.jpg"
                print(f"OK    {nome}  ({destino.stat().st_size // 1024} KB)")
            except Exception as e:
                print(f"ERRO  {nome}: não consegui ler {origem.name} ({e})")
        if not foto:
            sem_foto.append(nome)
        lista.append({"nome": nome, "foto": foto})

    (saida / "participantes.json").write_text(
        json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")

    html = Path(__file__).with_name("reveal.html")
    if html.exists() and html.resolve() != (saida / "reveal.html").resolve():
        shutil.copy(html, saida / "reveal.html")
    capa = Path(__file__).with_name("capa.jpg")  # imagem da prévia do link no WhatsApp
    if capa.exists() and capa.resolve() != (saida / "capa.jpg").resolve():
        shutil.copy(capa, saida / "capa.jpg")
    if a.base:
        # A prévia do WhatsApp exige endereço completo da capa: aponta para onde a pasta vai ficar.
        base = a.base.rstrip("/") + "/"
        pagina = saida / "reveal.html"
        txt = pagina.read_text(encoding="utf-8")
        novo = txt.replace("https://phceccato.github.io/amigo-secreto/", base)
        if novo == txt:
            print("AVISO: não achei o endereço antigo no reveal.html; prévia não ajustada.")
        pagina.write_text(novo, encoding="utf-8")
        print(f"Prévia do link ajustada para {base}")
    # Netlify: o WhatsApp Web monta a prévia do link dentro do navegador de quem envia, então a
    # página e a capa precisam de CORS liberado (o GitHub Pages já manda isso por padrão).
    # Os buscadores ficam de fora pelo <meta name="robots" content="noindex"> do reveal.html.
    (saida / "_headers").write_text("/*\n  Access-Control-Allow-Origin: *\n", encoding="utf-8")

    if sem_foto:
        print("\nSem foto (vai aparecer um círculo com as iniciais):", ", ".join(sem_foto))
    if originais:
        print("Arquivos que não bateram com nenhum nome:",
              ", ".join(p.name for p in originais.values()))
    print(f"\nPronto! Arraste a pasta '{saida}' inteira no Netlify (fotos e nomes NÃO vão "
          f"para o GitHub). Veja 'Fotos no Netlify' no LEIAME.md.")


if __name__ == "__main__":
    main()
