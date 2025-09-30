from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# Configuração do banco de dados PostgreSQL
app.config['SECRET_KEY'] = 'chave_segura_123'
# Se estiver usando pg8000 (recomendado para evitar problemas de compilação):
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+pg8000://postgres:2007@localhost:5432/lavanderia_db'
# Se estiver usando psycopg2-binary:
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:2007@localhost:5432/lavanderia_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================
# MODELOS DO BANCO
# ==========================
class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    apto = db.Column(db.String(20), nullable=False)

class Agendamento(db.Model):
    __tablename__ = 'agendamentos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    apto = db.Column(db.String(20), nullable=False)
    data = db.Column(db.String(20), nullable=False)
    horario = db.Column(db.String(10), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

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

        if Cliente.query.filter(db.func.lower(Cliente.nome) == nome.lower(), Cliente.apto == apto).first():
            return jsonify({"erro": "Cliente já cadastrado."}), 409

        novo_cliente = Cliente(nome=nome, apto=apto)
        db.session.add(novo_cliente)
        db.session.commit()

        return jsonify({"mensagem": "Cliente cadastrado com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": "Erro ao processar a requisição: " + str(e)}), 500

@app.route('/consultar', methods=['GET'])
def consultar():
    nome_busca = request.args.get('nome', '').strip().lower()
    data_busca = request.args.get('data', '').strip()
    
    if data_busca:
        # Busca por data específica
        agendamentos = Agendamento.query.filter_by(data=data_busca).all()
    elif nome_busca:
        # Busca por nome
        agendamentos = Agendamento.query.filter(db.func.lower(Agendamento.nome).like(f"%{nome_busca}%")).all()
    else:
        # Retorna todos
        agendamentos = Agendamento.query.all()
    
    return jsonify([{
        "nome": ag.nome,
        "apto": ag.apto,
        "data": ag.data,
        "horario": ag.horario
    } for ag in agendamentos])

@app.route('/desmarcar', methods=['POST'])
def desmarcar():
    try:
        nome = request.form.get('nome')
        apto = request.form.get('apto')
        
        if not nome or not apto:
            return "Dados incompletos", 400

        Cliente.query.filter(db.func.lower(Cliente.nome) == nome.lower(), Cliente.apto == apto).delete()
        Agendamento.query.filter(db.func.lower(Agendamento.nome) == nome.lower(), Agendamento.apto == apto).delete()
        db.session.commit()

        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        return f"Erro ao desmarcar cliente: {e}", 500

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
        
        # Garante que o cliente existe
        cliente = Cliente.query.filter(db.func.lower(Cliente.nome) == nome.lower(), Cliente.apto == apto).first()
        if not cliente:
            cliente = Cliente(nome=nome, apto=apto)
            db.session.add(cliente)
            db.session.commit()

        # Permitir até 2 pessoas por horário/data
        ocupados_mesmo_horario = Agendamento.query.filter_by(data=data, horario=horario).count()
        if ocupados_mesmo_horario >= 2:
            return jsonify({"erro": "Horário já ocupado por 2 pessoas"}), 409

        novo_agendamento = Agendamento(
            nome=nome,
            apto=apto,
            data=data,
            horario=horario
        )
        db.session.add(novo_agendamento)
        db.session.commit()

        return jsonify({"mensagem": "Agendamento realizado"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": "Erro ao agendar: " + str(e)}), 500

@app.route('/horarios', methods=['GET'])
def horarios():
    data = request.args.get('data')
    if not data:
        return jsonify({"erro": "Data não especificada."}), 400

    horarios_lavanderia = ["07:00", "10:00", "13:00", "16:00", "19:00", "22:00"]
    ocupacao = {h: 0 for h in horarios_lavanderia}
    agendamentos = Agendamento.query.filter_by(data=data).all()
    for ag in agendamentos:
        if ag.horario in ocupacao:
            ocupacao[ag.horario] += 1

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

        Agendamento.query.filter(
            db.func.lower(Agendamento.nome) == nome.lower(),
            Agendamento.apto == apto,
            Agendamento.data == data,
            Agendamento.horario == horario
        ).delete()
        db.session.commit()

        return jsonify({"mensagem": "Agendamento removido"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": f"Erro ao remover agendamento: {e}"}), 500

@app.route('/entregas')
def entregas():
    return render_template('entregas.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
