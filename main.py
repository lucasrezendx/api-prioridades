from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import pool
import os

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------
# ⚙️ Configuração do banco PostgreSQL (Supabase)
# ------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ Variável DATABASE_URL não configurada.")

# Força SSL se não estiver presente
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "&sslmode=require" if "?" in DATABASE_URL else "?sslmode=require"

# Cria um pool de conexões fixo
try:
    connection_pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=DATABASE_URL
    )
    print("✅ Pool de conexões PostgreSQL inicializado com sucesso.")
except Exception as e:
    print("❌ Erro ao criar pool de conexões:", e)
    raise

def get_connection():
    """Obtém uma conexão do pool"""
    return connection_pool.getconn()

def release_connection(conn):
    """Libera a conexão de volta ao pool"""
    if conn:
        connection_pool.putconn(conn)

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
    "CRESOL CONECTA": 3
}
LIMITE_PADRAO = 2

# ------------------------------------------------------
# 🧱 Inicializa tabela
# ------------------------------------------------------
def init_db():
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
    release_connection(conn)
    print("✅ Tabela 'prioridades' verificada/criada com sucesso.")

# ------------------------------------------------------
# 🧹 Limpeza
# ------------------------------------------------------
def limpar_registros_antigos():
    conn = get_connection()
    cursor = conn.cursor()
    limite = datetime.now() - timedelta(days=14)
    cursor.execute("DELETE FROM prioridades WHERE data < %s", (limite,))
    apagados = cursor.rowcount
    conn.commit()
    release_connection(conn)
    print(f"🧹 {apagados} registros antigos removidos (anteriores a {limite:%d/%m/%Y}).")

# ------------------------------------------------------
# 📅 Contagem semanal
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
    release_connection(conn)
    return total

# ------------------------------------------------------
# Rotas Flask
# ------------------------------------------------------
@app.route("/consultar_prioridades/<agencia>")
def consultar_prioridades(agencia):
    try:
        total = contar_prioridades_semana(agencia)
        limite = LIMITES_AGENCIAS.get(agencia.upper().strip(), LIMITE_PADRAO)
        atingiu = "Sim" if total >= limite else "Não"
        return jsonify({
            "agencia": agencia,
            "total_semana": total,
            "limite_semana": limite,
            "atingiu_limite": atingiu
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/limites")
def limites():
    return jsonify({**LIMITES_AGENCIAS, "_PADRAO_": LIMITE_PADRAO})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ------------------------------------------------------
# Inicialização automática
# ------------------------------------------------------
with app.app_context():
    init_db()
    limpar_registros_antigos()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
