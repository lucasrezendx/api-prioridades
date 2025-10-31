from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import psycopg2
import os
import traceback

app = Flask(__name__)
CORS(app)

# Configuração do banco PostgreSQL (Supabase)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    if not DATABASE_URL:
        raise ValueError("❌ Variável de ambiente DATABASE_URL não configurada.")
    conn_str = DATABASE_URL
    if "sslmode" not in conn_str:
        if "?" in conn_str:
            conn_str += "&sslmode=require"
        else:
            conn_str += "?sslmode=require"
    return psycopg2.connect(conn_str)

# Dicionário de limites por agência
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
    if not agencia:
        return LIMITE_PADRAO
    return AGENCIA_LIMITES.get(agencia.upper().strip(), LIMITE_PADRAO)

# Limpa registros antigos (mais de 14 dias)
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
        traceback.print_exc()

# Conta prioridades da semana
def contar_prioridades_semana(agencia):
    conn = get_connection()
    cursor = conn.cursor()
    hoje = datetime.now()
    segunda = hoje - timedelta(days=hoje.weekday())
    segunda = datetime(segunda.year, segunda.month, segunda.day)
    cursor.execute("""
        SELECT COUNT(*) FROM prioridades
        WHERE agencia = %s AND prioridade = 'Sim' AND data >= %s
    """, (agencia, segunda))
    total = cursor.fetchone()[0]
    conn.close()
    return total

@app.route("/")
def home():
    return jsonify({"mensagem": "API de Prioridades ativa!"})

@app.route("/consultar_prioridades/<agencia>")
def consultar_prioridades(agencia):
    try:
        total = contar_prioridades_semana(agencia)
        limite = obter_limite_agencia(agencia)
        atingiu = total >= limite
        return jsonify({
            "agencia": agencia,
            "total_semana": total,
            "limite": limite,
            "atingiu_limite": atingiu
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

@app.route("/registrar_prioridade", methods=["POST"])
def registrar_prioridade():
    try:
        dados = request.json
        if not dados:
            return jsonify({"erro": "JSON inválido."}), 400

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
                "mensagem": "Prioridade 'Não' não é registrada.",
                "total_semana": total,
                "limite": limite
            })

        if total >= limite:
            return jsonify({
                "permitido": False,
                "mensagem": f"Limite de {limite} prioridades atingido para {agencia}.",
                "total_semana": total
            })

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prioridades (agencia, processo_id, prioridade, data)
            VALUES (%s, %s, %s, %s)
        """, (agencia, processo_id, "Sim", datetime.now()))
        conn.commit()
        conn.close()

        return jsonify({
            "permitido": True,
            "mensagem": "Prioridade registrada com sucesso.",
            "total_semana": total + 1,
            "limite": limite
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

@app.route("/status")
def status():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prioridades")
        total = cursor.fetchone()[0]
        conn.close()
        return jsonify({"status": "ok", "total_registros": total})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "erro", "detalhes": str(e)}), 500

with app.app_context():
    limpar_registros_antigos()

# Necessário para o Vercel reconhecer o app Flask
handler = app
