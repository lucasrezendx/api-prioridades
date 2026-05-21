from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from supabase import create_client
import os

app = Flask(__name__)
CORS(app)

# Permite que rotas funcionem mesmo com barra final
app.url_map.strict_slashes = False

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
# 🏦 Limites por agência
# ------------------------------------------------------
LIMITES_AGENCIAS = {
    "CORONEL VIVIDA": 5,
    "HONÓRIO SERPA": 3,
    "MANGUEIRINHA": 5,
    "CORONEL DOMINGOS SOARES": 3,
    "PALMAS": 3,
    "CLEVELÂNDIA": 5,
    "MARIÓPOLIS": 3,
    "PATO BRANCO": 5,
    "PATO BRANCO SUL": 5,
    "PATO III": 3,
    "SORRISO": 5,
    "SINOP": 5,
    "LUCAS DO RIO VERDE": 5,
    "VERA": 3,
    "JUARA": 3,
    "TAPURAH": 2,
    "GUARANTA DO NORTE": 3,
    "JUINA": 2,
    "ALTA FLORESTA": 2,
    "COLIDER": 2,
    "CONECTA": 3
}

LIMITE_PADRAO = 2

# ------------------------------------------------------
# 🧹 Remover registros antigos
# ------------------------------------------------------
def limpar_registros_antigos():
    try:
        hoje = datetime.utcnow()
        segunda_atual = hoje - timedelta(days=hoje.weekday())
        segunda_atual = datetime(segunda_atual.year, segunda_atual.month, segunda_atual.day)
        segunda_iso = segunda_atual.isoformat()

        res = (
            supabase.table(TABLE_NAME)
            .delete()
            .lt("data", segunda_iso)
            .execute()
        )

        apagados = len(res.data or [])
        print(f"🧹 {apagados} registros removidos (anteriores à segunda-feira atual).")

    except Exception as e:
        print("❌ Erro ao limpar registros antigos:", e)

# ------------------------------------------------------
# ⚖️ Limite da agência
# ------------------------------------------------------
def get_limite_agencia(agencia):
    return LIMITES_AGENCIAS.get(agencia.upper().strip(), LIMITE_PADRAO)

# ------------------------------------------------------
# 📅 Contar prioridades da semana
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
# 🔎 Verifica processo existente
# ------------------------------------------------------
def processo_ja_registrado(processo_id):
    try:
        if not processo_id:
            return False

        res = (
            supabase.table(TABLE_NAME)
            .select("id")
            .eq("processo_id", processo_id)
            .execute()
        )
        return len(res.data or []) > 0
    except Exception as e:
        print("❌ Erro ao verificar processo existente:", e)
        return False

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
# 📝 Registrar prioridade
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
                "mensagem": "Prioridade marcada como 'Não' — não registrada.",
                "total_semana": total,
                "limite_semana": limite
            })

        if processo_ja_registrado(processo_id):
            return jsonify({
                "permitido": False,
                "mensagem": f"O processo {processo_id} já possui prioridade registrada.",
                "total_semana": total,
                "limite_semana": limite
            })

        if total >= limite:
            return jsonify({
                "permitido": False,
                "mensagem": f"A agência {agencia} já atingiu o limite semanal ({limite}).",
                "total_semana": total,
                "limite_semana": limite
            })

        novo = {
            "agencia": agencia,
            "processo_id": processo_id,
            "prioridade": "Sim",
            "data": datetime.utcnow().isoformat()
        }
        supabase.table(TABLE_NAME).insert(novo).execute()

        total += 1

        return jsonify({
            "permitido": True,
            "mensagem": "Prioridade registrada com sucesso.",
            "total_semana": total,
            "limite_semana": limite,
            "atingiu_limite": "Sim" if total >= limite else "Não"
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# ------------------------------------------------------
# 📋 Listar limites
# ------------------------------------------------------
@app.route("/limites", methods=["GET"])
def listar_limites():
    return jsonify({**LIMITES_AGENCIAS, "_PADRAO_": LIMITE_PADRAO})

# ------------------------------------------------------
# 🧽 Limpeza manual (AGORA FUNCIONA PELO NAVEGADOR)
# ------------------------------------------------------
@app.route("/limpar_banco", methods=["GET", "POST", "OPTIONS"])
def rota_limpar_banco():
    # Preflight CORS
    if request.method == "OPTIONS":
        return ('', 204)

    # Executar limpeza (GET ou POST)
    limpar_registros_antigos()

    return jsonify({"mensagem": "Limpeza executada com sucesso."})

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
