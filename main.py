from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from psycopg2 import pool
import psycopg2
import os
import time

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------
# ⚙️ Configuração do banco PostgreSQL (Supabase)
# ------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ Variável DATABASE_URL não configurada.")

# Força SSL
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "&sslmode=require" if "?" in DATABASE_URL else "?sslmode=require"

connection_pool = None


def init_connection_pool():
    """Inicializa o pool de conexões com retry automático."""
    global connection_pool
    for attempt in range(3):
        try:
            connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 5, DATABASE_URL, connect_timeout=5
            )
            print("✅ Pool de conexões inicializado com sucesso.")
            return
        except Exception as e:
            print(f"⚠️ Erro ao inicializar pool (tentativa {attempt+1}/3): {e}")
            time.sleep(2)
    raise Exception("❌ Falha ao criar pool de conexões com o banco.")


def get_connection():
    """Obtém uma conexão ativa do pool, recriando se necessário."""
    global connection_pool
    if connection_pool is None:
        init_connection_pool()
    try:
        return connection_pool.getconn()
    except Exception as e:
        print("⚠️ Erro ao obter conexão, recriando pool:", e)
        init_connection_pool()
        return connection_pool.getconn()


def release_connection(conn):
    """Devolve a conexão ao pool."""
    global connection_pool
    if connection_pool and conn:
        try:
            connection_pool.putconn(conn)
        except Exception as e:
            print("⚠️ Erro ao devolver conexão ao pool:", e)


# ------------------------------------------------------
# 🏦 Limites por agência
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
    "CRESOL CONECTA": 3,
}
LIMITE_PADRAO = 2


# ------------------------------------------------------
# 🧱 Cria a tabela se não existir
# ------------------------------------------------------
def init_db():
    conn = get_connection()
    try:
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
        print("✅ Tabela 'prioridades' verificada/criada com sucesso.")
    except Exception as e:
        print("❌ Erro ao criar tabela 'prioridades':", e)
    finally:
        release_connection(conn)


# ------------------------------------------------------
# 🧹 Remove registros antigos
# ------------------------------------------------------
def limpar_registros_antigos():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        limite = datetime.now() - timedelta(days=14)
        cursor.execute("DELETE FROM prioridades WHERE data < %s", (limite,))
        apagados = cursor.rowcount
        conn.commit()
        print(f"🧹 {apagados} registros antigos removidos (anteriores a {limite:%d/%m/%Y}).")
    except Exception as e:
        print("❌ Erro ao limpar registros antigos:", e)
    finally:
        release_connection(conn)


# ------------------------------------------------------
# ⚖️ Funções auxiliares
# ------------------------------------------------------
def get_limite_agencia(agencia):
    return LIMITES_AGENCIAS.get(agencia.upper().strip(), LIMITE_PADRAO)


def contar_prioridades_semana(agencia):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        hoje = datetime.now()
        segunda_atual = hoje - timedelta(days=hoje.weekday())
        segunda_atual = datetime(segunda_atual.year, segunda_atual.month, segunda_atual.day)
        cursor.execute("""
            SELECT COUNT(*) FROM prioridades
            WHERE UPPER(agencia) = UPPER(%s) AND prioridade = 'Sim' AND data >= %s
        """, (agencia, segunda_atual))
        total = cursor.fetchone()[0]
        return total
    except Exception as e:
        print("⚠️ Erro ao contar prioridades:", e)
        return 0
    finally:
        release_connection(conn)


# ------------------------------------------------------
# 🔎 Rotas Flask
# ------------------------------------------------------
@app.route("/")
def home():
    return jsonify({"status": "API online ✅"})


@app.route("/consultar_prioridades/<agencia>", methods=["GET"])
def consultar_prioridades(agencia):
    total = contar_prioridades_semana(agencia)
    limite = get_limite_agencia(agencia)
    atingiu = "Sim" if total >= limite else "Não"
    return jsonify({
        "agencia": agencia,
        "total_semana": total,
        "limite_semana": limite,
        "atingiu_limite": atingiu
    })


@app.route("/registrar_prioridade", methods=["POST"])
def registrar_prioridade():
    dados = request.json
    if not dados:
        return jsonify({"erro": "Envie um JSON."}), 400

    agencia = dados.get("agencia")
    prioridade = dados.get("prioridade")
    processo_id = dados.get("processo_id")

    if not agencia or prioridade not in ["Sim", "Não"]:
        return jsonify({"erro": "Campos obrigatórios: agencia e prioridade ('Sim'/'Não')."}), 400

    total = contar_prioridades_semana(agencia)
    limite = get_limite_agencia(agencia)

    if prioridade == "Não":
        return jsonify({"permitido": True, "mensagem": "Prioridade 'Não' não registrada."})

    if total >= limite:
        return jsonify({
            "permitido": False,
            "mensagem": f"A agência {agencia} já atingiu o limite semanal ({limite}).",
            "total_semana": total,
            "limite_semana": limite
        })

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prioridades (agencia, processo_id, prioridade, data)
            VALUES (%s, %s, %s, %s)
        """, (agencia, processo_id, "Sim", datetime.now()))
        conn.commit()
        print(f"✅ Prioridade registrada para {agencia}.")
    except Exception as e:
        print("❌ Erro ao registrar prioridade:", e)
        return jsonify({"erro": "Erro interno ao registrar."}), 500
    finally:
        release_connection(conn)

    total += 1
    atingiu = "Sim" if total >= limite else "Não"

    return jsonify({
        "permitido": True,
        "mensagem": "Prioridade registrada com sucesso.",
        "total_semana": total,
        "limite_semana": limite,
        "atingiu_limite": atingiu
    })


@app.route("/limites")
def limites():
    return jsonify({**LIMITES_AGENCIAS, "_PADRAO_": LIMITE_PADRAO})


# ------------------------------------------------------
# 🚀 Inicialização
# ------------------------------------------------------
with app.app_context():
    init_connection_pool()
    init_db()
    limpar_registros_antigos()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
