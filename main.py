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
# 🧱 Dicionário de limites por agência
# ------------------------------------------------------
AGENCIA_LIMITES = {
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


def obter_limite_agencia(agencia: str) -> int:
    """Retorna o limite configurado da agência ou o padrão."""
    if not agencia:
        return LIMITE_PADRAO
    return AGENCIA_LIMITES.get(agencia.upper().strip(), LIMITE_PADRAO)


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
        print(f"🧹 {apagados} registros antigos removidos.")
    except Exception as e:
        print("❌ Erro ao limpar registros antigos:", e)


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
    limite = obter_limite_agencia(agencia)
    possui_limite = "Sim" if total >= limite else "Não"
    return jsonify({
        "agencia": agencia,
        "total_semana": total,
        "limite": limite,
        "atingiu_limite": possui_limite
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

    limite = obter_limite_agencia(agencia)
    total = contar_prioridades_semana(agencia)

    if prioridade == "Não":
        return jsonify({
            "permitido": True,
            "mensagem": "Prioridade marcada como 'Não' — não registrada no banco.",
            "total_semana": total,
            "limite": limite
        })

    if total >= limite:
        return jsonify({
            "permitido": False,
            "mensagem": f"A agência {agencia} já atingiu seu limite semanal de {limite} prioridades.",
            "total_semana": total,
            "limite": limite
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
    atingiu = "Sim" if total >= limite else "Não"

    return jsonify({
        "permitido": True,
        "mensagem": "Prioridade 'Sim' registrada com sucesso.",
        "total_semana": total,
        "limite": limite,
        "atingiu_limite": atingiu
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
# 📊 Status do sistema
# ------------------------------------------------------
@app.route("/status", methods=["GET"])
def status_sistema():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prioridades")
        total_registros = cursor.fetchone()[0]
        conn.close()

        hoje = datetime.now()
        segunda_atual = hoje - timedelta(days=hoje.weekday())
        segunda_atual = datetime(segunda_atual.year, segunda_atual.month, segunda_atual.day)

        return jsonify({
            "status": "✅ Sistema em execução",
            "total_registros": total_registros,
            "segunda_referencia": segunda_atual.strftime("%Y-%m-%d"),
            "dias_retenção": 14
        })
    except Exception as e:
        return jsonify({"status": "❌ Erro ao obter status", "detalhes": str(e)}), 500


# ------------------------------------------------------
# Inicialização opcional (limpeza automática)
# ------------------------------------------------------
with app.app_context():
    limpar_registros_antigos()
