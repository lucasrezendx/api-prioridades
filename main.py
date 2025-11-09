from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
from supabase import create_client
import os

# -------------------------
# CONFIGURAÇÕES INICIAIS
# -------------------------
app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Nome da tabela no Supabase
TABLE_NAME = "prioridades"

# -------------------------
# FUNÇÕES AUXILIARES
# -------------------------

def limpar_registros_antigos():
    """Apaga registros com mais de 14 dias"""
    limite_data = (datetime.utcnow() - timedelta(days=14)).isoformat()
    supabase.table(TABLE_NAME).delete().lt("data_criacao", limite_data).execute()

def limitar_registros(max_registros=1000):
    """Mantém o número máximo de registros"""
    res = supabase.table(TABLE_NAME).select("id, data_criacao").order("data_criacao", desc=False).execute()
    registros = res.data or []
    if len(registros) > max_registros:
        ids_para_apagar = [r["id"] for r in registros[:len(registros) - max_registros]]
        supabase.table(TABLE_NAME).delete().in_("id", ids_para_apagar).execute()

def criar_tabela_se_nao_existir():
    """
    O Supabase cria as tabelas via SQL no painel,
    então aqui apenas garantimos que o código não quebre.
    """
    try:
        supabase.table(TABLE_NAME).select("*").limit(1).execute()
    except Exception as e:
        print("⚠️ Certifique-se de que a tabela 'prioridades' existe no Supabase:", e)

# -------------------------
# ROTAS DA API
# -------------------------

@app.route("/consultar_prioridades", methods=["GET"])
def consultar_prioridades():
    """Lista todas as prioridades"""
    try:
        limpar_registros_antigos()
        limitar_registros()

        res = supabase.table(TABLE_NAME).select("*").order("data_criacao", desc=True).execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/registrar_prioridade", methods=["POST"])
def registrar_prioridade():
    """Registra uma nova prioridade"""
    try:
        dados = request.get_json()
        descricao = dados.get("descricao")

        if not descricao:
            return jsonify({"erro": "Campo 'descricao' é obrigatório."}), 400

        novo_registro = {
            "descricao": descricao,
            "data_criacao": datetime.utcnow().isoformat()
        }

        supabase.table(TABLE_NAME).insert(novo_registro).execute()

        limpar_registros_antigos()
        limitar_registros()

        return jsonify({"mensagem": "Prioridade registrada com sucesso!"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "API online e conectada ao Supabase via HTTPS!"})


# -------------------------
# INICIALIZAÇÃO
# -------------------------
if __name__ == "__main__":
    criar_tabela_se_nao_existir()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
