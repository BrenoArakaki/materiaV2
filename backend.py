import os
from flask import Flask, request, jsonify
from flask_cors import CORS

from materia_v2 import (
    PDF_PATH,
    CSV_CACHE,
    garantir_csv,
    carregar_linhas_csv,
    listar_materias_base,
    extrair_professores_por_materia,
    buscar_professor,
    pegar_reviews,
    pegar_percentual_A,
    calcular_distribuicao_completa
)

app = Flask(__name__)
CORS(app)  # permite o React (rodando em outra origem/porta) chamar essa API

# Carrega o CSV uma vez, na subida do servidor
garantir_csv(PDF_PATH, CSV_CACHE)
LINHAS = carregar_linhas_csv(CSV_CACHE)

@app.route("/api/materias")
def api_materias():
    termo = request.args.get("q", "").strip()
    if not termo:
        return jsonify({"opcoes": []})

    opcoes = listar_materias_base(LINHAS, termo)
    return jsonify({"opcoes": opcoes})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    global LINHAS # Permite atualizar a variável global sem reiniciar o servidor
    
    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"erro": "Nenhum arquivo selecionado"}), 400
        
    if file and file.filename.endswith('.pdf'):
        # 1. Salva o novo PDF por cima do antigo
        file.save(PDF_PATH)
        
        # 2. Apaga o cache CSV antigo, se existir
        if os.path.exists(CSV_CACHE):
            os.remove(CSV_CACHE)
            
        try:
            # 3. Força a extração novamente e atualiza a variável global
            garantir_csv(PDF_PATH, CSV_CACHE)
            LINHAS = carregar_linhas_csv(CSV_CACHE)
            
            return jsonify({"mensagem": "PDF atualizado e processado com sucesso!"}), 200
        except Exception as e:
            return jsonify({"erro": f"Erro ao processar o PDF: {str(e)}"}), 500
            
    return jsonify({"erro": "Formato inválido. Por favor, envie um arquivo .pdf"}), 400


@app.route("/api/ranking")
def api_ranking():
    materia = request.args.get("materia", "").strip()
    if not materia:
        return jsonify({"erro": "parâmetro 'materia' é obrigatório"}), 400

    encontrados = extrair_professores_por_materia(LINHAS, materia)
    if not encontrados:
        return jsonify({"ranking": [], "avisos": ["Nenhum professor encontrado para essa matéria."]})

    ranking = []
    avisos = []

    for item in encontrados:
        nome_pdf = item["professor_pdf"]
        try:
            busca = buscar_professor(nome_pdf)

            if busca.get("total", 0) == 0 or not busca.get("data"):
                avisos.append(f"Professor não encontrado na API: {nome_pdf}")
                continue

            prof_api = busca["data"][0]
            teacher_id = prof_api["_id"]
            nome_api = prof_api["name"]

            reviews = pegar_reviews(teacher_id)
            a_percent = pegar_percentual_A(reviews)
            distribuicao = calcular_distribuicao_completa(reviews)  # <--- CHAMADA DA FUNÇÃO NOVA

            url = f"https://www.ufabcnext.com/app/reviews?q={nome_api}&teacherId={teacher_id}"

            ranking.append({
                "materia": item["materia"],
                "professor": nome_api,
                "teacher_id": teacher_id,
                "a_percent": round(a_percent, 2),
                "distribuicao": distribuicao,  # <--- ENVIO DA DISTRIBUIÇÃO PRO FRONT
                "url": url,
                "turma": item["turma_completa"],
                "papel": item["papel"],
            })

        except Exception as e:
            avisos.append(f"Erro com {nome_pdf}: {e}")

    # remove duplicados por professor, mantendo o de maior % A
    unicos = {}
    for prof in ranking:
        tid = prof["teacher_id"]
        if tid not in unicos or prof["a_percent"] > unicos[tid]["a_percent"]:
            unicos[tid] = prof

    ranking_final = sorted(unicos.values(), key=lambda x: x["a_percent"], reverse=True)

    return jsonify({"ranking": ranking_final, "avisos": avisos})


if __name__ == "__main__":
    if not os.environ.get("UFABC_TOKEN"):
        print("AVISO: variável UFABC_TOKEN não definida. As buscas na API vão falhar.")
    app.run(port=5000, debug=True)