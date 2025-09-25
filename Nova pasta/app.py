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
    if not os.path.exists(caminho_arquivo):
        return []
    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
        return json.load(f)

def salvar_dados(dados, caminho_arquivo):
    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# ==========================
# ROTAS DO FLASK
# ==========================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    try:
        dados = request.get_json()
        nome = dados.get('nome')
        apto = dados.get('apto')
        
        if not nome or not apto:
            return jsonify({"erro": "Nome e apartamento são obrigatórios."}), 400

        clientes = carregar_dados(ARQUIVO_CLIENTES)

        if any(c['nome'].lower() == nome.lower() and c['apto'] == apto for c in clientes):
            return jsonify({"erro": "Cliente já cadastrado."}), 409

        clientes.append({'nome': nome, 'apto': apto})
        salvar_dados(clientes, ARQUIVO_CLIENTES)

        return jsonify({"mensagem": "Cliente cadastrado com sucesso!"}), 200
    except Exception as e:
        return jsonify({"erro": "Erro ao processar a requisição: " + str(e)}), 500

@app.route('/consultar', methods=['GET'])
def consultar():
    nome_busca = request.args.get('nome', '').strip().lower()
    agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)

    if not nome_busca:
        return jsonify(agendamentos)

    clientes_encontrados = [ag for ag in agendamentos if nome_busca in ag['nome'].lower()]
    return jsonify(clientes_encontrados)

@app.route('/desmarcar', methods=['POST'])
def desmarcar():
    try:
        nome = request.form.get('nome')
        apto = request.form.get('apto')
        
        if not nome or not apto:
            return "Dados incompletos", 400

        clientes = carregar_dados(ARQUIVO_CLIENTES)
        novos_clientes = [c for c in clientes if not (c['nome'].lower() == nome.lower() and c['apto'] == apto)]
        salvar_dados(novos_clientes, ARQUIVO_CLIENTES)
        
        agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)
        novos_agendamentos = [ag for ag in agendamentos if not (ag['nome'].lower() == nome.lower() and ag['apto'] == apto)]
        salvar_dados(novos_agendamentos, ARQUIVO_AGENDAMENTOS)

        return redirect(url_for('index'))
    except Exception as e:
        return f"Erro ao desmarcar cliente: {e}", 500

# --- ALTERADO: Agendar permite até 2 pessoas por horário ---
@app.route('/agendar', methods=['POST'])
def agendar():
    try:
        dados = request.form
        nome = dados.get('nome')
        apto = dados.get('apto')
        data = dados.get('data')
        horario = dados.get('horario')

        if not nome or not apto or not data or not horario:
            return jsonify({"erro": "Dados incompletos"}), 400
        
        clientes_cadastrados = carregar_dados(ARQUIVO_CLIENTES)
        cliente_existe = any(c['nome'].lower() == nome.lower() and c['apto'] == apto for c in clientes_cadastrados)
        if not cliente_existe:
            clientes_cadastrados.append({'nome': nome, 'apto': apto})
            salvar_dados(clientes_cadastrados, ARQUIVO_CLIENTES)

        agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)

        # --- ALTERAÇÃO: permitir até 2 pessoas por horário ---
        ocupados_mesmo_horario = [ag for ag in agendamentos if ag['data'] == data and ag['horario'] == horario]
        if len(ocupados_mesmo_horario) >= 2:
            return jsonify({"erro": "Horário já ocupado por 2 pessoas"}), 409

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

# --- ALTERADO: Horários considera ocupados apenas se tiver 2 pessoas ---
@app.route('/horarios', methods=['GET'])
def horarios():
    data = request.args.get('data')
    if not data:
        return jsonify({"erro": "Data não especificada."}), 400

    horarios_lavanderia = ["07:00", "10:00", "13:00", "16:00", "19:00", "22:00"]
    agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS)

    ocupacao = {h: 0 for h in horarios_lavanderia}
    for ag in agendamentos:
        if ag['data'] == data and ag['horario'] in ocupacao:
            ocupacao[ag['horario']] += 1

    disponiveis = [h for h, qtd in ocupacao.items() if qtd < 2]
    ocupados = [h for h, qtd in ocupacao.items() if qtd >= 2]

    return jsonify({
        "disponiveis": disponiveis,
        "ocupados": ocupados
    })

@app.route('/desmarcar_horario', methods=['POST'])
def desmarcar_horario():
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

@app.route('/entregas')
def entregas():
    return render_template('entregas.html')

if __name__ == '__main__':
    if not os.path.exists(ARQUIVO_CLIENTES):
        salvar_dados([], ARQUIVO_CLIENTES)
    if not os.path.exists(ARQUIVO_AGENDAMENTOS):
        salvar_dados([], ARQUIVO_AGENDAMENTOS)
    app.run(host='0.0.0.0', port=5000, debug=True)
