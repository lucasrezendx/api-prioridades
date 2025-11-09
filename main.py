import os
import psycopg2
from psycopg2 import pool
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import time

# ==============================
# 🔧 CONFIGURAÇÃO DO APP
# ==============================
app = Flask(__name__)
CORS(app)

# ==============================
# 🗄️ CONFIGURAÇÃO DO BANCO (SUPABASE)
# ==============================
DB_URL = "postgres://postgres.cvjwrmmjinaxdquowboq:32323815Soares@aws-1-us-east-2.pooler.supabase.com:5432/postgres"

connection_pool = None


def init_connection_pool():
    """Inicializa o pool de conexões."""
    global connection_pool
    if connection_pool is None:
        try:
            connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10, DB_URL, connect_timeout=5
            )
            print("✅ Pool de conexões inicializado com sucesso.")
        except Exception as e:
            print("❌ Erro ao inicializar pool:", e)


def get_connection():
    """Obtém uma conexão do pool, com retry automático."""
    global connection_pool
    if connection_pool is None:
        init_connection_pool()

    for attempt in range(3):
        try:
            conn = connection_pool.getconn()
            return conn
        except Exception as e:
            print(f"⚠️ Erro ao pegar conexão (tentativa {attempt + 1}): {e}")
            time.sleep(1)
            if attempt == 2:
                # Recria o pool se falhar 3 vezes
                print("♻️ Recriando pool de conexões...")
                init_connection_pool()
    raise Exception("Falha ao conectar ao banco após várias tentativas")


def release_connection(conn):
    """Libera uma conexão de volta ao pool."""
    global connection_pool
    if connection_pool and conn:
        try:
            connection_pool.putconn(conn)
        except Exception as e:
            print("⚠️ Erro ao liberar conexão:", e)


# ==============================
# 🧹 MANUTENÇÃO AUTOMÁTICA
# ==============================
def limpar_registros_antigos():
    """Remove registros com mais de 14 dias."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        limite = datetime.now() - timedelta(days=14)
        cur.execute("DELETE FROM prioridades WHERE data_criacao < %s", (limite,))
        removidos = cur.rowcount
        conn.commit()
        print(f"🧹 {removidos} registros antigos removidos (anteriores a {limite.date()}).")
    except Exception as e:
        print("⚠️ Erro ao limpar registros antigos:", e)
    finally:
        release_connection(conn)


# ==============================
# 🏗️ INICIALIZAÇÃO DA TABELA
# ==============================
def criar_tabela_prioridades():
    """Cria a tabela se não existir."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prioridades (
                id SERIAL PRIMARY KEY,
                agencia VARCHAR(255),
                prioridade VARCHAR(255),
                data_criacao TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
        print("✅ Tabela 'prioridades' verificada/criada com sucesso.")
    except Exception as e:
        print("❌ Erro ao criar tabela:", e)
    finally:
        release_connection(conn)


# ==============================
# 📊 FUNÇÕES DE CONSULTA
# ==============================
def contar_prioridades_semana(agencia):
    """Conta registros da semana atual por agência."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        inicio_semana = datetime.now() - timedelta(days=datetime.now().weekday())
        cur.execute("""
            SELECT COUNT(*) FROM prioridades
            WHERE agencia = %s AND data_criacao >= %s;
        """, (agencia, inicio_semana))
        total = cur.fetchone()[0]
        return total
    except Exception as e:
        print("⚠️ Erro ao contar prioridades:", e)
        return 0
    finally:
        release_connection(conn)


def listar_prioridades(agencia):
    """Lista todas as prioridades de uma agência."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, prioridade, data_criacao
            FROM prioridades
            WHERE agencia = %s
            ORDER BY data_criacao DESC;
        """, (agencia,))
        rows = cur.fetchall()
        return [
            {"id": r[0], "prioridade": r[1], "data_criacao": r[2].isoformat()}
            for r in rows
        ]
    except Exception as e:
        print("⚠️ Erro ao listar prioridades:", e)
        return []
    finally:
        release_connection(conn)


# ==============================
# 🌐 ROTAS FLASK
# ==============================
@app.route("/")
def home():
    return jsonify({"status": "API online ✅"})


@app.route("/consultar_prioridades/<agencia>")
def consultar_prioridades(agencia):
    """Consulta as prioridades por agência."""
    try:
        total = contar_prioridades_semana(agencia)
        prioridades = listar_prioridades(agencia)
        return jsonify({
            "agencia": agencia,
            "total_semana": total,
            "prioridades": prioridades
        })
    except Exception as e:
        print("❌ Erro na rota /consultar_prioridades:", e)
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/limites")
def limites():
    """Exemplo de rota que retorna limites de alguma lógica."""
    data = {
        "limite_semanal": 20,
        "limite_diario": 5,
        "mensagem": "Limites carregados com sucesso"
    }
    return jsonify(data)


# ==============================
# 🚀 INICIALIZAÇÃO
# ==============================
if __name__ == "__main__":
    init_connection_pool()
    criar_tabela_prioridades()
    limpar_registros_antigos()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
