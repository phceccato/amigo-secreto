#!/usr/bin/env python3
"""Amigo Secreto com links opacos enviados por WhatsApp.

O resultado NUNCA é impresso, gravado ou logado: existe só na memória e,
cifrado, dentro do link que vai na conversa de cada pessoa.

Uso:
  python3 sorteio.py --teste
  python3 sorteio.py participantes.csv --url https://SEU-USUARIO.github.io/amigo-secreto/reveal.html --eu "Seu Nome"
"""
import argparse
import base64
import csv
import secrets
import shlex
import subprocess
import sys
import webbrowser
from urllib.parse import quote

BLOCO = 64  # tamanho fixo (bytes) para não vazar o tamanho do nome

MENSAGEM = (
    "🎄 *Amigo Secreto Família Ceccato* 🎄\n\n"
    "Oi, {nome}! Chegou a hora do sorteio do Amigo Secreto! 🎁\n\n"
    "Toque no link abaixo para fazer o seu sorteio e prepare o coração:\n"
    "{link}\n\n"
    "Guarde segredo até o dia da revelação! 🤫✨"
)

# Celular de mais de um participante: cada um recebe a sua mensagem, e esta linha vai logo
# depois do link para ninguém abrir o do outro. NÃO ponha no topo: com o link muito abaixo
# (~250 caracteres) o WhatsApp Web não monta a prévia com a imagem.
AVISO_COMPARTILHADO = ("👉 *Este link é só de {nome}.* Este celular recebe mais de um link: "
                       "abra só o seu.\n\n")


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def cifrar(nome: str) -> str:
    dados = nome.encode("utf-8")
    if len(dados) > BLOCO:
        raise ValueError(f"Nome muito longo (máx. {BLOCO} bytes): {nome}")
    dados = dados.ljust(BLOCO, b"\0")
    # O WhatsApp lê "_texto_" como itálico e quebra o link: sorteia a chave
    # de novo até o token sair sem "_" (cerca de 1 em 15 tentativas serve).
    while True:
        chave = secrets.token_bytes(BLOCO)  # pad de uso único
        cifrado = bytes(a ^ b for a, b in zip(dados, chave))
        token = b64u(chave + cifrado)
        if "_" not in token:
            return token


def decifrar(token: str) -> str:
    raw = b64u_dec(token)
    chave, cifrado = raw[:BLOCO], raw[BLOCO:]
    return bytes(a ^ b for a, b in zip(chave, cifrado)).rstrip(b"\0").decode("utf-8")


def endereco_unico(url: str) -> str:
    """Põe um código aleatório antes do '#' para cada link ser um endereço novo.

    O WhatsApp Web guarda a prévia por endereço (sem o '#') e, ao repetir um endereço,
    manda a mensagem sem a imagem. O código é aleatório e não tem relação com o sorteio.
    """
    return f"{url}{'&' if '?' in url else '?'}k={secrets.token_hex(4)}"


def telefone(txt: str) -> str:
    d = "".join(c for c in txt if c.isdigit())
    if txt.strip().startswith("+"):
        # Com "+" o número já vem com o código do país (ex.: +1 734 ... dos EUA): usa como está.
        if len(d) < 10:
            raise ValueError(f"Telefone inválido: {txt!r}")
        return d
    if len(d) in (10, 11):
        d = "55" + d
    if len(d) < 12:
        raise ValueError(f"Telefone inválido: {txt!r} (use DDD; código do país opcional)")
    return d


def ler_participantes(caminho):
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f))
    pessoas = []
    for l in linhas:
        nome = (l.get("nome") or "").strip()
        if not nome:
            continue
        proib = {x.strip() for x in (l.get("nao_pode_tirar") or "").split(";") if x.strip()}
        pessoas.append({"nome": nome, "tel": telefone(l.get("telefone") or ""), "proib": proib})
    nomes = [p["nome"] for p in pessoas]
    if len(set(nomes)) != len(nomes):
        sys.exit("Erro: há nomes repetidos. Diferencie (ex.: 'Ana S.' e 'Ana M.').")
    if len(pessoas) < 3:
        sys.exit("Erro: são necessários pelo menos 3 participantes.")
    for p in pessoas:
        desconhecidos = p["proib"] - set(nomes)
        if desconhecidos:
            sys.exit(f"Erro: 'nao_pode_tirar' de {p['nome']} cita nome inexistente: {desconhecidos}")
    return pessoas


def ciclo_unico(perm):
    """True se a permutação forma um único ciclo (a->b->...->a passando por todos)."""
    i, n = perm[0], 1
    while i != 0:
        i = perm[i]
        n += 1
    return n == len(perm)


def valido(nomes, proib, perm):
    return (all(perm[i] != i and nomes[perm[i]] not in proib[i] for i in range(len(nomes)))
            and ciclo_unico(perm))


def sortear(nomes, proib, tentativas=200_000):
    rng = secrets.SystemRandom()
    idx = list(range(len(nomes)))
    for _ in range(tentativas):
        perm = idx[:]
        rng.shuffle(perm)
        if valido(nomes, proib, perm):
            return perm
    sys.exit("Não consegui um sorteio válido: restrições impossíveis?")


def abrir(url, cmd=None):
    if cmd:
        subprocess.Popen(shlex.split(cmd) + [url])
    else:
        webbrowser.open(url)


def modo_teste():
    nomes = ["Ana", "Bruno", "Carla", "Davi", "Eva", "Fábio", "Gil", "Helena"]
    proib = [set() for _ in nomes]
    proib[0].add("Bruno"); proib[1].add("Ana")  # casal fictício
    for _ in range(5000):
        perm = sortear(nomes, proib)
        assert sorted(perm) == list(range(len(nomes))), "não é permutação"
        assert valido(nomes, proib, perm), "violou regra"
        assert ciclo_unico(perm), "sorteio fechou em mais de um grupo"
    assert not ciclo_unico([1, 0, 3, 2]), "ciclo_unico não detectou 2 grupos"
    assert ciclo_unico([1, 2, 3, 0]), "ciclo_unico rejeitou ciclo único"
    for n in nomes + ["José da Conceição Álvares"]:
        for _ in range(50):
            t = cifrar(n)
            assert decifrar(t) == n
            assert "_" not in t, "token com '_' quebra o link no WhatsApp"
    perm = sortear(nomes, proib)
    token = cifrar(nomes[perm[0]])
    print("OK: 5000 sorteios válidos (ninguém tira a si mesmo, restrições respeitadas, ciclo único).")
    print("OK: cifra/decifra confere.")
    print(f"Exemplo FICTÍCIO: {nomes[0]} tirou {decifrar(token)}")
    print(f"Token de exemplo ({len(token)} caracteres): {token[:30]}...")


def com_aviso(texto, nome):
    """Põe o AVISO_COMPARTILHADO logo depois do link (a linha que começa com http)."""
    linhas = texto.split("\n")
    i = next(i for i, l in enumerate(linhas) if l.startswith("http"))
    return "\n".join(linhas[:i + 1]) + "\n\n" + AVISO_COMPARTILHADO.format(nome=nome).rstrip("\n") + "\n" + "\n".join(linhas[i + 1:])


def conversa(tel, texto=None):
    # Direto no WhatsApp Web: o redirecionamento do wa.me troca emojis por "�".
    url = f"https://web.whatsapp.com/send?phone={tel}"
    return url + (f"&text={quote(texto)}" if texto else "")


def problemas_telefones(caminho):
    """Lista (nome, problema) e telefones repetidos, sem sortear nada."""
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        linhas = [l for l in csv.DictReader(f) if (l.get("nome") or "").strip()]
    probs, por_tel, ok = [], {}, []
    for l in linhas:
        nome, bruto = l["nome"].strip(), (l.get("telefone") or "").strip()
        if not bruto:
            probs.append((nome, "sem telefone"))
            continue
        try:
            t = telefone(bruto)
        except ValueError:
            probs.append((nome, "telefone inválido"))
            continue
        if t.startswith("55") and not (len(t) == 13 and t[4] == "9"):
            probs.append((nome, "aviso: celular sem o 9 na frente; confira se a conversa abre"))
        por_tel.setdefault(t, []).append(nome)
        ok.append((nome, t))
    repetidos = [ns for ns in por_tel.values() if len(ns) > 1]
    return probs, repetidos, ok


def verificar(caminho, navegador=None):
    probs, repetidos, ok = problemas_telefones(caminho)
    print(f"{len(ok) + sum(1 for _, p in probs if not p.startswith('aviso'))} participantes no CSV.\n")
    for nome, p in probs:
        print(f"  {nome}: {p}")
    for ns in repetidos:
        print(f"  Mesmo telefone: {', '.join(ns)} (cada um recebe a sua mensagem, com o nome no topo)")
    if not probs and not repetidos:
        print("  Nenhum problema de formato.")
    print("\nAgora abro cada conversa no WhatsApp Web SEM mensagem e SEM link (nada é sorteado).")
    print('Se aparecer "O número de telefone compartilhado por url é inválido", anote o nome.')
    vistos = set()
    for nome, tel in ok:
        if tel in vistos:
            continue
        vistos.add(tel)
        abrir(conversa(tel), navegador)
        if input(f"  {nome}: a conversa abriu? [Enter = sim / n = não] ").strip().lower().startswith("n"):
            print(f"    -> corrija o telefone de {nome} no CSV.")
    print("\nVerificação concluída. Corrija o CSV e rode de novo até não sobrar problema.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo", nargs="?")
    ap.add_argument("--url", help="endereço público da reveal.html")
    ap.add_argument("--eu", help="seu nome (seu resultado abre direto no navegador)")
    ap.add_argument("--navegador", help='comando do navegador, ex.: "firefox --private-window"')
    ap.add_argument("--teste", action="store_true", help="roda testes com nomes fictícios")
    ap.add_argument("--verificar", action="store_true",
                    help="confere os telefones e abre cada conversa SEM mensagem (não sorteia)")
    a = ap.parse_args()

    if a.verificar:
        if not a.arquivo:
            ap.error("informe o arquivo CSV")
        return verificar(a.arquivo, a.navegador)

    if a.teste:
        return modo_teste()
    if not a.arquivo or not a.url:
        ap.error("informe o arquivo CSV e --url (ou use --teste)")

    probs, repetidos, _ = problemas_telefones(a.arquivo)
    graves = [(n, x) for n, x in probs if not x.startswith("aviso")]
    if graves:
        for n, x in graves:
            print(f"  {n}: {x}")
        sys.exit("Corrija o CSV antes de sortear (detalhes: python3 sorteio.py ARQUIVO --verificar).")
    pessoas = ler_participantes(a.arquivo)
    nomes = [p["nome"] for p in pessoas]
    if a.eu and a.eu not in nomes:
        sys.exit(f"Erro: --eu '{a.eu}' não está na lista.")
    proib = [p["proib"] for p in pessoas]

    perm = sortear(nomes, proib)
    assert valido(nomes, proib, perm)
    print(f"Sorteio válido para {len(pessoas)} participantes. Nenhum resultado será exibido.\n")

    compartilhado = {}
    for p in pessoas:
        compartilhado[p["tel"]] = compartilhado.get(p["tel"], 0) + 1
    for i, p in enumerate(pessoas):
        link = f"{endereco_unico(a.url)}#{cifrar(nomes[perm[i]])}"
        if p["nome"] == a.eu:
            print("Abrindo o SEU resultado no navegador...")
            abrir(link, a.navegador)
        else:
            texto = MENSAGEM.format(nome=p["nome"], link=link)
            if compartilhado[p["tel"]] > 1:
                texto = com_aviso(texto, p["nome"])
            print(f"Abrindo conversa com {p['nome']}: ESPERE a imagem do presente aparecer "
                  "acima da mensagem e só então clique em Enviar.\n"
                  "  (Sem imagem depois de uns 10 s? Digite um espaço no fim da mensagem para o "
                  "WhatsApp tentar de novo. Nunca mexa no link: ele quebra.)")
            abrir(conversa(p["tel"], texto), a.navegador)
        del link
        input("  Enter para continuar... ")

    print("\nPronto! Todos os envios foram feitos. Nada foi gravado em disco.")


if __name__ == "__main__":
    main()
