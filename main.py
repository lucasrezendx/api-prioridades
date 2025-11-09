from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from supabase import create_client
import os

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------
# ⚙️ Configuração do Supabase
# ------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Variáveis SUPABASE_URL e SUPABASE_KEY não configuradas.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "prioridades"

# ------------------------------------------------------
# 🏦 Limites por agência (iguais ao seu código original)
# ------------------------------------------------------
LIMITES_AGENCIAS = {
    "CRESOL CORONEL VIVIDA": 5,
    "CRESOL HONORIO SERPA": 3,
    "CRESOL MANGUEIRINHA": 5,
    "CRESOL CORONEL DOMINGOS SOARES": 3,
    "CRESOL PALMAS": 3,
    "CRESOL CLEVELANDIA": 5,
    "CRESOL MARIOPOLIS": 3,
    "CRESOL PATO BRANCO": 5,
    "CRESOL PATO BRANCO SUL": 5,
    "CRESOL PATO III": 3,
    "CRESOL SORRISO": 5,
    "CRESOL SINOP": 5,
    "CRESOL LUCAS DO RIO VERDE": 5,
    "CRESOL VERA": 3,
    "CRESOL JUARA": 3,
    "CRESOL TAPURAH": 2,
    "CRESOL GUARANTA DO NORTE": 3,
    "CRESOL JUINA": 2,
    "CRESOL ALTA FLORESTA": 2,
    "CRESOL COLÍDER": 2,
    "CRESOL CONECTA": 3
}

LIMITE_PADRAO = 2


# ------------------------------------------------------
# 🧹 Remove registros com mais de 14 dias
# ------------------------------------------------------
def limpar_registros_antigos():
    try:
        limite = (datetime.utcnow() - timedelta(days=14)).isoformat()
        res = supabase.table(TABLE_NAME).delete().lt("data", limite).execute()
        apagados = len(res.data or [])
        print(f"🧹 {apagados} registros antigos removidos (anteriores a {limite}).")
    except Exception as e:
        print("❌ Erro ao limpar registros antigos:", e)


# ------------------------------------------------------
# ⚖️ Retorna o limite da agência
# ------------------------------------------------------
def get_limite_agencia(agencia):
    return LIMITES_AGENCIAS.get(agencia.upper().strip(), LIMITE_PADRAO)


# ------------------------------------------------------
# 📅 Conta quantas prioridades "Sim" a agência teve na semana atual
# ------------------------------------------------------
def contar_prioridades_semana(agencia):
    try:
        hoje = datetime.utcnow()
        segunda_atual = hoje - timedelta(days=hoje.weekday())
        segunda_atual = datetime(segunda_atual.year, segunda_atual.month, segunda_atual.day)
        segunda_iso = segunda_atual.isoformat()

        res = (
            supabase.table(TABLE_NAME)
            .select("id")
            .eq("agencia", agencia)
            .eq("prioridade", "Sim")
            .gte("data", segunda_iso)
            .execute()
        )

        return len(res.data or [])
    except Exception as e:
        print("❌ Erro ao contar prioridades:", e)
        return 0


# ------------------------------------------------------
# 🔎 Consulta prioridades por agência
# ------------------------------------------------------
@app.route("/consultar_prioridades/<agencia>", methods=["GET"])
def consultar_prioridades(agencia):
    total = contar_prioridades_semana(agencia)
    limite = get_limite_agencia(agencia)
    atingiu_limite = "Sim" if total >= limite else "Não"
    return jsonify({
        "agencia": agencia,
        "total_semana": total,
        "limite_semana": limite,
        "atingiu_limite": atingiu_limite
    })


# ------------------------------------------------------
# 📝 Registra prioridade (somente "Sim")
# ------------------------------------------------------
@app.route("/registrar_prioridade", methods=["POST"])
def registrar_prioridade():
    try:
        dados = request.json
        if not dados:
            return jsonify({"erro": "Requisição inválida: envie um JSON."}), 400

        agencia = dados.get("agencia")
        prioridade = dados.get("prioridade")
        processo_id = dados.get("processo_id")

        if not agencia or prioridade not in ["Sim", "Não"]:
            return jsonify({"erro": "Campos obrigatórios: agencia e prioridade ('Sim' ou 'Não')."}), 400

        total = contar_prioridades_semana(agencia)
        limite = get_limite_agencia(agencia)

        if prioridade == "Não":
            return jsonify({
                "permitido": True,
                "mensagem": "Prioridade marcada como 'Não' — não registrada no banco.",
                "total_semana": total,
                "limite_semana": limite
            })

        if total >= limite:
            return jsonify({
                "permitido": False,
                "mensagem": f"A agência {agencia} já atingiu seu limite semanal ({limite}).",
                "total_semana": total,
                "limite_semana": limite
            })

        # Inserir novo registro
        novo = {
            "agencia": agencia,
            "processo_id": processo_id,
            "prioridade": "Sim",
            "data": datetime.utcnow().isoformat()
        }
        supabase.table(TABLE_NAME).insert(novo).execute()

        total += 1
        atingiu_limite = "Sim" if total >= limite else "Não"

        return jsonify({
            "permitido": True,
            "mensagem": "Prioridade 'Sim' registrada com sucesso.",
            "total_semana": total,
            "limite_semana": limite,
            "atingiu_limite": atingiu_limite
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ------------------------------------------------------
# 📋 Lista todas as agências e seus limites
# ------------------------------------------------------
@app.route("/limites", methods=["GET"])
def listar_limites():
    return jsonify({**LIMITES_AGENCIAS, "_PADRAO_": LIMITE_PADRAO})


# ------------------------------------------------------
# 🧽 Rota manual para limpar registros antigos
# ------------------------------------------------------
@app.route("/limpar_banco", methods=["POST"])
def rota_limpar_banco():
    limpar_registros_antigos()
    return jsonify({"mensagem": "Limpeza de registros antigos executada com sucesso."})


# ------------------------------------------------------
# 🚀 Inicialização automática
# ------------------------------------------------------
with app.app_context():
    limpar_registros_antigos()

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "API online e conectada ao Supabase!"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
