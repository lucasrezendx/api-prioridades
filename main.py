from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------
# ⚙️ Configuração do banco PostgreSQL (Render)
# ------------------------------------------------------
DB_CONFIG = {
    "host": os.environ.get("DB_HOST"),
    "dbname": os.environ.get("DB_NAME"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASS"),
    "port": os.environ.get("DB_PORT", 5432)
}


# ------------------------------------------------------
# 🧱 Conecta ao banco
# ------------------------------------------------------
def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# ------------------------------------------------------
# 🧱 Cria a tabela, se ainda não existir
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
                prioridade TEXT CHECK(prioridade IN ('Sim', 'Não')),
                data TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("✅ Tabela 'prioridades' verificada/criada com sucesso.")
    except Exception as e:
        print("❌ Erro ao criar tabela 'prioridades':", e)


# ------------------------------------------------------
# 📅 Conta quantas prioridades "Sim" uma agência teve nos últimos 7 dias
# ------------------------------------------------------
def contar_prioridades_semana(agencia):
    conn = get_connection()
    cursor = conn.cursor()
    inicio_semana = datetime.now() - timedelta(days=7)
    cursor.execute("""
        SELECT COUNT(*) FROM prioridades
        WHERE agencia = %s AND prioridade = 'Sim' AND data >= %s
    """, (agencia, inicio_semana))
    total = cursor.fetchone()[0]
    conn.close()
    return total


# ------------------------------------------------------
# 🔎 Consulta prioridades por agência
# ------------------------------------------------------
@app.route("/consultar_prioridades/<agencia>", methods=["GET"])
def consultar_prioridades(agencia):
    total = contar_prioridades_semana(agencia)
    possui5 = "Sim" if total >= 5 else "Não"
    return jsonify({
        "agencia": agencia,
        "total_semana": total,
        "possui5": possui5
    })


# ------------------------------------------------------
# 📝 Registra prioridade
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
    if prioridade == "Sim" and total >= 5:
        return jsonify({
            "permitido": False,
            "mensagem": f"A agência {agencia} já atingiu 5 prioridades nesta semana.",
            "total_semana": total
        })

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO prioridades (agencia, processo_id, prioridade, data)
        VALUES (%s, %s, %s, %s)
    """, (agencia, processo_id, prioridade, datetime.now()))
    conn.commit()
    conn.close()

    if prioridade == "Sim":
        total += 1
    possui5 = "Sim" if total >= 5 else "Não"

    return jsonify({
        "permitido": True,
        "mensagem": "Prioridade registrada com sucesso.",
        "total_semana": total,
        "possui5": possui5
    })


# ------------------------------------------------------
# 📋 Lista todas as agências registradas
# ------------------------------------------------------
@app.route("/listar_agencias", methods=["GET"])
def listar_agencias():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT agencia FROM prioridades")
    agencias = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(agencias)


# ------------------------------------------------------
# 🚀 Inicializa app + garante que a tabela exista no Render
# ------------------------------------------------------
with app.app_context():
    init_db()  # <- AGORA é executado mesmo quando o Render usa gunicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
