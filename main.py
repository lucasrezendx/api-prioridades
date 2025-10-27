from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)
DB = "prioridades.db"

def init_db():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prioridades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agencia TEXT NOT NULL,
            processo_id TEXT,
            prioridade TEXT,
            data DATETIME
        )
    """)
    conn.commit()
    conn.close()

init_db()

def contar_prioridades_semana(agencia):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    inicio_semana = datetime.now() - timedelta(days=7)
    cursor.execute("""
        SELECT COUNT(*) FROM prioridades
        WHERE agencia = ? AND prioridade = 'sim' AND data >= ?
    """, (agencia, inicio_semana))
    total = cursor.fetchone()[0]
    conn.close()
    return total

@app.route("/consultar_prioridades/<agencia>", methods=["GET"])
def consultar_prioridades(agencia):
    total = contar_prioridades_semana(agencia)
    possui5 = "sim" if total >= 5 else "não"
    return jsonify({
        "agencia": agencia,
        "total_semana": total,
        "possui5": possui5
    })

@app.route("/registrar_prioridade", methods=["POST"])
def registrar_prioridade():
    dados = request.json
    agencia = dados.get("agencia")
    prioridade = dados.get("prioridade")
    processo_id = dados.get("processo_id")

    if not agencia or prioridade not in ["sim", "não"]:
        return jsonify({"erro": "Dados inválidos"}), 400

    total = contar_prioridades_semana(agencia)
    if prioridade == "sim" and total >= 5:
        return jsonify({
            "permitido": False,
            "mensagem": f"A agência {agencia} já atingiu 5 prioridades nesta semana.",
            "total_semana": total
        })

    if prioridade == "sim":
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prioridades (agencia, processo_id, prioridade, data)
            VALUES (?, ?, ?, ?)
        """, (agencia, processo_id, prioridade, datetime.now()))
        conn.commit()
        conn.close()
        total += 1

    possui5 = "sim" if total >= 5 else "não"
    return jsonify({
        "permitido": True,
        "total_semana": total,
        "possui5": possui5
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
