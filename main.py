from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)
DB = "prioridades.db"

# ------------------------------------------------------
# 🧱 Inicializa o banco de dados
# ------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prioridades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agencia TEXT NOT NULL,
            processo_id TEXT,
            prioridade TEXT CHECK(prioridade IN ('sim', 'não')),
            data TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ------------------------------------------------------
# 📅 Conta quantas prioridades "sim" uma agência teve nos últimos 7 dias
# ------------------------------------------------------
def contar_prioridades_semana(agencia):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    inicio_semana = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute("""
        SELECT COUNT(*) FROM prioridades
        WHERE agencia = ? AND prioridade = 'sim' AND data >= ?
    """, (agencia, inicio_semana))
    total = cursor.fetchone()[0]
    conn.close()
    return total

# ------------------------------------------------------
# 🔎 Consulta a quantidade de prioridades por agência
# ------------------------------------------------------
@app.route("/consultar_prioridades/<agencia>", methods=["GET"])
def consultar_prioridades(agencia):
    total = contar_prioridades_semana(agencia)
    possui5 = "sim" if total >= 5 else "não"
    return jsonify({
        "agencia": agencia,
        "total_semana": total,
        "possui5": possui5
    })

# ------------------------------------------------------
# 📝 Registra uma prioridade
# ------------------------------------------------------
@app.route("/registrar_prioridade", methods=["POST"])
def registrar_prioridade():
    dados = request.json
    if not dados:
        return jsonify({"erro": "Requisição inválida: envie um JSON."}), 400

    agencia = dados.get("agencia")
    prioridade = dados.get("prioridade")
    processo_id = dados.get("processo_id")

    if not agencia or prioridade not in ["sim", "não"]:
        return jsonify({"erro": "Campos obrigatórios: agencia e prioridade ('sim' ou 'não')."}), 400

    total = contar_prioridades_semana(agencia)

    # Limita a 5 prioridades por semana
    if prioridade == "sim" and total >= 5:
        return jsonify({
            "permitido": False,
            "mensagem": f"A agência {agencia} já atingiu 5 prioridades nesta semana.",
            "total_semana": total
        })

    # Insere o registro
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO prioridades (agencia, processo_id, prioridade, data)
        VALUES (?, ?, ?, ?)
    """, (agencia, processo_id, prioridade, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    if prioridade == "sim":
        total += 1

    possui5 = "sim" if total >= 5 else "não"
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
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prioridades")
    agencias = [row[0] for row in cursor.fetchall()]
    conn.close()

    resultado = []
    for agencia in agencias:
        resultado.append({
            "id": agencia.id
        })

    return jsonify(resultado)

# ------------------------------------------------------
# 🚀 Inicializa o servidor
# ------------------------------------------------------
if __name__ == "__main__":
    # Para rodar localmente:
    app.run(host="0.0.0.0", port=8080, debug=True)
    # Se quiser expor em um container, use:
    # app.run(host="0.0.0.0", port=8080, debug=True)
