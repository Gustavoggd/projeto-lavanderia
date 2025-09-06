from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

# ==========================
# CONSTANTES DE ARQUIVOS
# ==========================
ARQUIVO_CLIENTES = 'clientes.json'
ARQUIVO_AGENDAMENTOS = 'agendamentos.json'

# ==========================
# FUNÇÕES AUXILIARES
# ==========================
def carregar_dados(caminho_arquivo):
    """Carrega dados de um arquivo JSON. Retorna uma lista vazia se o arquivo não existir."""
    if not os.path.exists(caminho_arquivo):
        return []
    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
        return json.load(f)

def salvar_dados(dados, caminho_arquivo):
    """Salva dados em um arquivo JSON."""
    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# ==========================
# ROTAS DO FLASK
# ==========================
@app.route('/')
def index():
    return render_template('index.html')

# --- Rota de Cadastro de Clientes (Removida do HTML, mas mantida no back-end) ---
@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    """Cadastra um novo cliente com nome e apartamento."""
    try:
        dados = request.get_json()
        nome = dados.get('nome')
        apto = dados.get('apto')
        
        if not nome or not apto:
            return jsonify({"erro": "Nome e apartamento são obrigatórios."}), 400

        clientes = carregar_dados(ARQUIVO_CLIENTES)

        # Evitar duplicidade de cliente
        if any(c['nome'].lower() == nome.lower() and c['apto'] == apto for c in clientes):
            return jsonify({"erro": "Cliente já cadastrado."}), 409

        clientes.append({'nome': nome, 'apto': apto})
        salvar_dados(clientes, ARQUIVO_CLIENTES)

        return jsonify({"mensagem": "Cliente cadastrado com sucesso!"}), 200

    except Exception as e:
        return jsonify({"erro": "Erro ao processar a requisição: " + str(e)}), 500

# --- Rota de Consulta de Clientes ---
@app.route('/consultar', methods=['GET'])
def consultar():
    """Consulta agendamentos de clientes. Permite busca por nome."""
    nome_busca = request.args.get('nome', '').strip().lower()
    
    agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)

    if not nome_busca:
        return jsonify(agendamentos)

    clientes_encontrados = [ag for ag in agendamentos if nome_busca in ag['nome'].lower()]
    
    return jsonify(clientes_encontrados)

# --- Rota de Desmarcar Cliente (do cadastro) ---
@app.route('/desmarcar', methods=['POST'])
def desmarcar():
    """Remove um cliente e todos os seus agendamentos."""
    try:
        nome = request.form.get('nome')
        apto = request.form.get('apto')
        
        if not nome or not apto:
            return "Dados incompletos", 400

        # Remove o cliente da lista de clientes
        clientes = carregar_dados(ARQUIVO_CLIENTES)
        novos_clientes = [c for c in clientes if not (c['nome'].lower() == nome.lower() and c['apto'] == apto)]
        salvar_dados(novos_clientes, ARQUIVO_CLIENTES)
        
        # Remove todos os agendamentos desse cliente
        agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)
        novos_agendamentos = [ag for ag in agendamentos if not (ag['nome'].lower() == nome.lower() and ag['apto'] == apto)]
        salvar_dados(novos_agendamentos, ARQUIVO_AGENDAMENTOS)

        return redirect(url_for('index'))
    except Exception as e:
        return f"Erro ao desmarcar cliente: {e}", 500

# --- Rota de Agendamento ---
@app.route('/agendar', methods=['POST'])
def agendar():
    """Realiza um agendamento de lavanderia para um cliente existente."""
    try:
        # AQUI FOI FEITA A CORREÇÃO:
        # O HTML envia dados como 'form-urlencoded', então usamos request.form
        dados = request.form
        nome = dados.get('nome')
        apto = dados.get('apto')
        data = dados.get('data')
        horario = dados.get('horario')

        if not nome or not apto or not data or not horario:
            return jsonify({"erro": "Dados incompletos"}), 400
        
        # AQUI FOI FEITA A CORREÇÃO:
        # Verificamos se o cliente já está cadastrado antes de prosseguir
        clientes_cadastrados = carregar_dados(ARQUIVO_CLIENTES)
        cliente_existe = any(c['nome'].lower() == nome.lower() and c['apto'] == apto for c in clientes_cadastrados)
        if not cliente_existe:
            # Se o cliente não existe, o agendamento o cadastra automaticamente
            clientes_cadastrados.append({'nome': nome, 'apto': apto})
            salvar_dados(clientes_cadastrados, ARQUIVO_CLIENTES)

        agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)

        # Valida se o horário já está ocupado
        for ag in agendamentos:
            if ag['data'] == data and ag['horario'] == horario:
                return jsonify({"erro": "Horário já ocupado"}), 409

        # Adiciona o novo agendamento
        novo_agendamento = {
            'nome': nome,
            'apto': apto,
            'data': data,
            'horario': horario
        }
        agendamentos.append(novo_agendamento)
        salvar_dados(agendamentos, ARQUIVO_AGENDAMENTOS)

        return jsonify({"mensagem": "Agendamento realizado"}), 200
    except Exception as e:
        return jsonify({"erro": "Erro ao agendar: " + str(e)}), 500

# --- Rota para Horários Disponíveis ---
@app.route('/horarios', methods=['GET'])
def horarios():
    """Retorna os horários disponíveis e ocupados para uma data específica."""
    data = request.args.get('data')
    if not data:
        return jsonify({"erro": "Data não especificada."}), 400

    horarios_lavanderia = ["07:00", "10:00", "13:00", "16:00", "19:00", "22:00"]
    agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)
    horarios_ocupados = [ag['horario'] for ag in agendamentos if ag['data'] == data]

    return jsonify({
        "disponiveis": [h for h in horarios_lavanderia if h not in horarios_ocupados],
        "ocupados": horarios_ocupados
    })

# --- Rota para Desmarcar um Horário Específico ---
@app.route('/desmarcar_horario', methods=['POST'])
def desmarcar_horario():
    """Remove um agendamento específico com base nos dados fornecidos pelo formulário."""
    try:
        dados = request.form
        nome = dados.get('nome')
        apto = dados.get('apto')
        data = dados.get('data')
        horario = dados.get('horario')

        if not all([nome, apto, data, horario]):
            return "Dados incompletos", 400

        agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)
        novos_agendamentos = [
            ag for ag in agendamentos
            if not (ag['nome'].lower() == nome.lower() and ag['apto'] == apto and ag['data'] == data and ag['horario'] == horario)
        ]
        
        salvar_dados(novos_agendamentos, ARQUIVO_AGENDAMENTOS)

        return jsonify({"mensagem": "Agendamento removido"}), 200

    except Exception as e:
        return jsonify({"erro": f"Erro ao remover agendamento: {e}"}), 500

# ==========================
# EXECUÇÃO DO APP
# ==========================
if __name__ == '__main__':
    # Cria os arquivos de dados se não existirem
    if not os.path.exists(ARQUIVO_CLIENTES):
        salvar_dados([], ARQUIVO_CLIENTES)
    if not os.path.exists(ARQUIVO_AGENDAMENTOS):
        salvar_dados([], ARQUIVO_AGENDAMENTOS)
    app.run(debug=True)