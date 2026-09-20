import re
import csv
import os
import pdfplumber
import requests
from urllib.parse import quote_plus

PDF_PATH = "matriculas_2026_2_turmas_ofertadas.pdf"
CSV_CACHE = "turmas.csv"
TOKEN = os.environ.get("UFABC_TOKEN", "")  # export UFABC_TOKEN=... antes de rodar

COLUNAS_DOCENTE = [
    "DOCENTE TEORIA",
    "DOCENTE TEORIA 2",
    "DOCENTE TEORIA 3",
    "DOCENTE PRÁTICA",
    "DOCENTE PRÁTICA 2",
    "DOCENTE PRÁTICA 3",
]

def calcular_distribuicao_completa(review_json):
    """Calcula o percentual de cada conceito (A, B, C, D, F, O) para o gráfico."""
    contagem = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0, "O": 0}
    
    try:
        dist = review_json["general"]["distribution"]
    except (KeyError, TypeError):
        return contagem

    total = 0
    temp_valores = {}
    
    for item in dist:
        conceito = item.get("conceito")
        qtd = item.get("amount", 0)
        if conceito:
            conceito = str(conceito).strip().upper()
            temp_valores[conceito] = qtd
            total += qtd

    if total == 0:
        return contagem

    for k in contagem:
        qtd = temp_valores.get(k, 0)
        contagem[k] = round((qtd / total) * 100, 2)

    return contagem


def materia_base(turma_texto):
    """Extrai o nome da matéria a partir da coluna TURMA, removendo o
    sufixo de turno/campus (ex.: 'A1-Matutino (SA)')."""
    texto = turma_texto.strip().replace("\n", " ")
    texto = re.split(r"\s+[A-Z]\d*-", texto, maxsplit=1)[0]
    return texto.strip()


def carregar_tabela(pdf_path):
    """Lê o PDF (export de Excel) como uma tabela estruturada.
    Muito mais robusto que parsear linha a linha: cada coluna já vem
    separada, sem depender de heurísticas para achar nomes."""
    header = None
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tabela in page.extract_tables():
                if not tabela:
                    continue
                if header is None:
                    header = [h.replace("\n", " ").strip() for h in tabela[0]]
                inicio = 1 if tabela[0][0] == "CURSO" else 0
                for linha in tabela[inicio:]:
                    rows.append(
                        [(c or "").replace("\n", " ").strip() for c in linha]
                    )

    return header, rows


def garantir_csv(pdf_path, csv_path):
    """Gera o CSV a partir do PDF apenas se ainda não existir
    (evita reprocessar o PDF toda vez que o script roda)."""
    if os.path.exists(csv_path):
        return

    header, rows = carregar_tabela(pdf_path)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def carregar_linhas_csv(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def listar_materias_base(linhas, termo_busca):
    termo_busca = termo_busca.upper().strip()
    vistos = set()
    opcoes = []

    for linha in linhas:
        base = materia_base(linha["TURMA"])
        if termo_busca in base.upper() and base not in vistos:
            vistos.add(base)
            opcoes.append(base)

    return sorted(opcoes)


def extrair_professores_por_materia(linhas, materia_escolhida):
    materia_escolhida = materia_escolhida.upper().strip()
    resultados = []
    vistos = set()

    for linha in linhas:
        if materia_base(linha["TURMA"]).upper() != materia_escolhida:
            continue

        for coluna in COLUNAS_DOCENTE:
            professor = linha.get(coluna, "").strip()
            if not professor:
                continue

            chave = (materia_escolhida, professor)
            if chave in vistos:
                continue
            vistos.add(chave)

            resultados.append({
                "materia": materia_base(linha["TURMA"]),
                "professor_pdf": professor,
                "codigo_turma": linha.get("CÓDIGO DE TURMA", ""),
                "turma_completa": linha["TURMA"],
                "papel": coluna,  # ex.: "DOCENTE TEORIA", "DOCENTE PRÁTICA 2"
            })

    return resultados


def buscar_professor(nome):
    url = "https://api.v2.ufabcnext.com/entities/teachers/search"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    r = requests.get(url, params={"q": nome}, headers=headers)
    r.raise_for_status()
    return r.json()


def pegar_reviews(teacher_id):
    url = f"https://api.v2.ufabcnext.com/entities/teachers/reviews/{teacher_id}"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


def pegar_percentual_A(review_json):
    dist = review_json["general"]["distribution"]
    total = 0
    qtd_a = 0

    for item in dist:
        qtd = item.get("amount", 0)
        total += qtd
        if item.get("conceito") == "A":
            qtd_a = qtd

    if total == 0:
        return 0

    return (qtd_a / total) * 100


def main():
    if not TOKEN:
        print("Defina a variável de ambiente UFABC_TOKEN antes de rodar.")
        return

    garantir_csv(PDF_PATH, CSV_CACHE)
    linhas = carregar_linhas_csv(CSV_CACHE)

    termo = input("Digite a matéria: ").strip()
    opcoes = listar_materias_base(linhas, termo)

    if not opcoes:
        print("Nenhuma matéria encontrada.")
        return

    print("\nEscolha a matéria:\n")
    for i, materia in enumerate(opcoes, start=1):
        print(f"{i}. {materia}")

    try:
        escolha = int(input("\nDigite o número: ")) - 1
        if escolha < 0 or escolha >= len(opcoes):
            print("Opção inválida.")
            return
    except ValueError:
        print("Digite um número válido.")
        return

    materia_escolhida = opcoes[escolha]
    encontrados = extrair_professores_por_materia(linhas, materia_escolhida)

    if not encontrados:
        print("Nenhum professor encontrado para essa matéria.")
        return

    ranking = []

    for item in encontrados:
        nome_pdf = item["professor_pdf"]

        try:
            busca = buscar_professor(nome_pdf)

            if busca["total"] == 0 or not busca["data"]:
                print(f"Professor não encontrado na API: {nome_pdf}")
                continue

            prof_api = busca["data"][0]
            teacher_id = prof_api["_id"]
            nome_api = prof_api["name"]

            reviews = pegar_reviews(teacher_id)
            a_percent = pegar_percentual_A(reviews)

            url = f"https://www.ufabcnext.com/app/reviews?q={quote_plus(nome_api)}&teacherId={teacher_id}"

            ranking.append({
                "materia": item["materia"],
                "professor": nome_api,
                "teacher_id": teacher_id,
                "A_percent": a_percent,
                "url": url,
                "turma": item["turma_completa"],
                "papel": item["papel"],
            })

        except Exception as e:
            print(f"Erro com {nome_pdf}: {e}")

    unicos = {}
    for prof in ranking:
        tid = prof["teacher_id"]
        if tid not in unicos or prof["A_percent"] > unicos[tid]["A_percent"]:
            unicos[tid] = prof

    ranking = list(unicos.values())
    ranking.sort(key=lambda x: x["A_percent"], reverse=True)

    print(f"\nRanking por percentual de A — {materia_escolhida}:\n")
    for i, prof in enumerate(ranking, start=1):
        print(f"{i}. {prof['professor']} ({prof['papel']}) -> {prof['A_percent']:.2f}% A")
        print(f"   Turma: {prof['turma']}")
        print(f"   Link: {prof['url']}")
        print()


if __name__ == "__main__":
    main()