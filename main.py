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
    if "sslmode" not in DATABASE_URL:
        if "?" in DATABASE_URL:
            conn_str = DATABASE_URL + "&sslmode=require"
        else:
            conn_str = DATABASE_URL + "?sslmode=require"
    else:
        conn_str = DATABASE_URL
    return psycopg2.connect(conn_str)


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
# 📅 Conta quantas prioridades "Sim" a agência teve na semana atual
# ------------------------------------------------------
def contar_prioridades_semana(agencia):
    conn = get_connection()
    cursor = conn.cursor()

    # Determina a segunda-feira da semana atual (início da contagem)
    hoje = datetime.now()
    segunda_atual = hoje - timedelta(days=hoje.weekday())  # weekday(): 0 = segunda
    segunda_atual = datetime(segunda_atual.year, segunda_atual.month, segunda_atual.day)

    cursor.execute("""
        SELECT COUNT(*) FROM prioridades
        WHERE agencia = %s AND prioridade = 'Sim' AND data >= %s
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
    possui5 = "Sim" if total >= 5 else "Não"
    return jsonify({
        "agencia": agencia,
        "total_semana": total,
        "possui5": possui5
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

    # ❌ Ignora prioridades "Não"
    if prioridade == "Não":
        total = contar_prioridades_semana(agencia)
        return jsonify({
            "permitido": True,
            "mensagem": "Prioridade marcada como 'Não' — não registrada no banco.",
            "total_semana": total,
            "possui5": "Sim" if total >= 5 else "Não"
        })

    # ✅ Verifica limite semanal antes de registrar
    total = contar_prioridades_semana(agencia)
    if total >= 5:
        return jsonify({
            "permitido": False,
            "mensagem": f"A agência {agencia} já atingiu 5 prioridades nesta semana.",
            "total_semana": total
        })

    # Registrar prioridade "Sim"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO prioridades (agencia, processo_id, prioridade, data)
        VALUES (%s, %s, %s, %s)
    """, (agencia, processo_id, "Sim", datetime.now()))
    conn.commit()
    conn.close()

    total += 1
    possui5 = "Sim" if total >= 5 else "Não"

    return jsonify({
        "permitido": True,
        "mensagem": "Prioridade 'Sim' registrada com sucesso.",
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
# 🧽 Rota manual opcional para limpar registros antigos
# ------------------------------------------------------
@app.route("/limpar_banco", methods=["POST"])
def rota_limpar_banco():
    limpar_registros_antigos()
    return jsonify({"mensagem": "Limpeza de registros antigos executada com sucesso."})


# ------------------------------------------------------
# 📊 Nova rota: status do sistema
# ------------------------------------------------------
@app.route("/status", methods=["GET"])
def status_sistema():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Segunda-feira de referência
        hoje = datetime.now()
        segunda_atual = hoje - timedelta(days=hoje.weekday())
        segunda_atual = datetime(segunda_atual.year, segunda_atual.month, segunda_atual.day)

        # Total de registros no banco
        cursor.execute("SELECT COUNT(*) FROM prioridades")
        total_registros = cursor.fetchone()[0]

        conn.close()

        return jsonify({
            "status": "✅ Sistema em execução",
            "segunda_referencia": segunda_atual.strftime("%Y-%m-%d"),
            "total_registros": total_registros,
            "dias_retenção_dados": 14,
            "mensagem": "As contagens são reiniciadas automaticamente toda segunda-feira."
        })
    except Exception as e:
        return jsonify({"status": "❌ Erro ao obter status", "detalhes": str(e)}), 500


# ------------------------------------------------------
# 🚀 Inicialização automática
# ------------------------------------------------------
with app.app_context():
    init_db()
    limpar_registros_antigos()  # limpa automaticamente ao iniciar

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
