from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------
# ⚙️ Configuração do banco PostgreSQL (Supabase)
# ------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    if not DATABASE_URL:
        raise ValueError("❌ Variável de ambiente DATABASE_URL não configurada.")
    conn_str = DATABASE_URL
    if "sslmode" not in conn_str:
        conn_str += "&sslmode=require" if "?" in conn_str else "?sslmode=require"
    return psycopg2.connect(conn_str)


# ------------------------------------------------------
# 🏦 Limites por agência (definidos no código)
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
# 🧱 Cria a tabela se não existir
# ------------------------------------------------------
def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prioridades (
                id SERIAL PRIMARY KEY,
                agencia TEXT NOT NULL,
                processo_id TEXT,
                prioridade TEXT CHECK(prioridade IN ('Sim')),
                data TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("✅ Tabela 'prioridades' verificada/criada com sucesso.")
    except Exception as e:
        print("❌ Erro ao criar tabela 'prioridades':", e)


# ------------------------------------------------------
# 🧹 Remove registros com mais de 14 dias
# ------------------------------------------------------
def limpar_registros_antigos():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        limite = datetime.now() - timedelta(days=14)
        cursor.execute("DELETE FROM prioridades WHERE data < %s", (limite,))
        apagados = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"🧹 {apagados} registros antigos removidos (anteriores a {limite:%d/%m/%Y}).")
    except Exception as e:
        print("❌ Erro ao limpar registros antigos:", e)


# ------------------------------------------------------
# ⚖️ Retorna o limite da agência (ou padrão se não estiver na lista)
# ------------------------------------------------------
def get_limite_agencia(agencia):
    return LIMITES_AGENCIAS.get(agencia.upper().strip(), LIMITE_PADRAO)


# ------------------------------------------------------
# 📅 Conta quantas prioridades "Sim" a agência teve na semana atual
# ------------------------------------------------------
def contar_prioridades_semana(agencia):
    conn = get_connection()
    cursor = conn.cursor()
    hoje = datetime.now()
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    segunda_atual = datetime(segunda_atual.year, segunda_atual.month, segunda_atual.day)

    cursor.execute("""
        SELECT COUNT(*) FROM prioridades
        WHERE UPPER(agencia) = UPPER(%s) AND prioridade = 'Sim' AND data >= %s
    """, (agencia, segunda_atual))
    total = cursor.fetchone()[0]
    conn.close()
    return total


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

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO prioridades (agencia, processo_id, prioridade, data)
        VALUES (%s, %s, %s, %s)
    """, (agencia, processo_id, "Sim", datetime.now()))
    conn.commit()
    conn.close()

    total += 1
    atingiu_limite = "Sim" if total >= limite else "Não"

    return jsonify({
        "permitido": True,
        "mensagem": "Prioridade 'Sim' registrada com sucesso.",
        "total_semana": total,
        "limite_semana": limite,
        "atingiu_limite": atingiu_limite
    })


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
    init_db()
    limpar_registros_antigos()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
