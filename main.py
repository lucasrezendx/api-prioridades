from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import sqlite3
import os

app = Flask(__name__)
CORS(app)

DB = "prioridades.db"

# ---------------------------------------
# Inicializa o banco se não existir
# ---------------------------------------
def init_db():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prioridades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agencia TEXT NOT NULL,
            processo_id TEXT,
            prioridade TEXT CHECK(prioridade IN ('Sim', 'Não')),
            data TEXT
        )
    """)
    conn.commit()
    conn.close()

# ---------------------------------------
# Conta prioridades da semana
# ---------------------------------------
def contar_prioridades_semana(agencia):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    inicio_semana = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute("""
        SELECT COUNT(*) FROM prioridades
        WHERE agencia = ? AND prioridade = 'Sim' AND data >= ?
    """, (agencia, inicio_semana))
    total = cursor.fetchone()[0]
    conn.close()
    return total

# ---------------------------------------
# Consulta
# ---------------------------------------
@app.route("/consultar_prioridades/<agencia>", methods=["GET"])
def consultar_prioridades(agencia):
    total = contar_prioridades_semana(agencia)
    possui5 = "Sim" if total >= 5 else "Não"
    return jsonify({
        "agencia": agencia,
        "total_semana": total,
        "possui5": possui5
    })

# ---------------------------------------
# Registrar
# ---------------------------------------
@app.route("/registrar_prioridade", methods=["POST"])
def registrar_prioridade():
    dados = request.json
    if not dados:
        return jsonify({"erro": "Envie um JSON válido."}), 400

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

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO prioridades (agencia, processo_id, prioridade, data)
        VALUES (?, ?, ?, ?)
    """, (agencia, processo_id, prioridade, datetime.now().isoformat()))
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

# ---------------------------------------
# Listar agências
# ---------------------------------------
@app.route("/listar_agencias", methods=["GET"])
def listar_agencias():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT agencia FROM prioridades")
    agencias = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(agencias)

# ---------------------------------------
# Iniciar servidor
# ---------------------------------------
# Garante que o banco existe mesmo no Render
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
