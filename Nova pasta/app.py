from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# Configuração do banco de dados PostgreSQL
app.config['SECRET_KEY'] = 'chave_segura_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+pg8000://postgres:2007@localhost:5432/lavanderia_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================
# LOGIN MANAGER
# ==========================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Você precisa fazer login para acessar esta página.'
login_manager.login_message_category = 'info'

# ==========================
# MODELOS DO BANCO
# ==========================
class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.senha_hash, senha)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

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
# ROTAS DE AUTENTICAÇÃO
# ==========================
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'GET':
        return render_template('registro.html')
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            email = request.form.get('email')
            senha = request.form.get('senha')
            
            if not nome or not email or not senha:
                return jsonify({"erro": "Preencha todos os campos"}), 400
            
            if Usuario.query.filter_by(email=email).first():
                return jsonify({"erro": "E-mail já cadastrado"}), 409
            
            usuario = Usuario(nome=nome, email=email)
            usuario.set_password(senha)
            db.session.add(usuario)
            db.session.commit()
            
            return jsonify({"mensagem": "Usuário cadastrado com sucesso!"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"erro": f"Erro ao cadastrar usuário: {str(e)}"}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            senha = request.form.get('senha')
            
            if not email or not senha:
                return jsonify({"erro": "Preencha e-mail e senha"}), 400
            
            usuario = Usuario.query.filter_by(email=email).first()
            
            if not usuario or not usuario.check_password(senha):
                return jsonify({"erro": "E-mail ou senha inválidos"}), 401
            
            login_user(usuario)
            return jsonify({"mensagem": "Login realizado com sucesso!"}), 200
        except Exception as e:
            return jsonify({"erro": f"Erro no login: {str(e)}"}), 500

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ==========================
# ROTAS PRINCIPAIS
# ==========================
@app.route('/')
def index():
    user_data = None
    if current_user.is_authenticated:
        user_data = {
            'nome': current_user.nome,
            'email': current_user.email
        }
    return render_template('index.html', user=user_data)

@app.route('/cadastrar', methods=['POST'])
@login_required
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
        agendamentos = Agendamento.query.filter_by(data=data_busca).all()
    elif nome_busca:
        agendamentos = Agendamento.query.filter(db.func.lower(Agendamento.nome).like(f"%{nome_busca}%")).all()
    else:
        agendamentos = Agendamento.query.all()
    
    return jsonify([{
        "nome": ag.nome,
        "apto": ag.apto,
        "data": ag.data,
        "horario": ag.horario
    } for ag in agendamentos])

@app.route('/desmarcar', methods=['POST'])
@login_required
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
@login_required
def agendar():
    try:
        dados = request.form
        nome = dados.get('nome')
        apto = dados.get('apto')
        data = dados.get('data')
        horario = dados.get('horario')

        if not nome or not apto or not data or not horario:
            return jsonify({"erro": "Dados incompletos"}), 400
        
        cliente = Cliente.query.filter(db.func.lower(Cliente.nome) == nome.lower(), Cliente.apto == apto).first()
        if not cliente:
            cliente = Cliente(nome=nome, apto=apto)
            db.session.add(cliente)
            db.session.commit()

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
        horarios_lavanderia = ["07:00", "10:00", "13:00", "16:00", "19:00", "22:00"]
        return jsonify({
            "disponiveis": horarios_lavanderia,
            "ocupados": []
        })

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
@login_required
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
@login_required
def entregas():
    user_data = {
        'nome': current_user.nome,
        'email': current_user.email
    }
    return render_template('entregas.html', user=user_data)

@app.route('/consultar_entregas', methods=['GET'])
@login_required
def consultar_entregas():
    cliente = request.args.get('cliente', '').strip()
    apartamento = request.args.get('apartamento', '').strip()
    
    # Por enquanto, retorna dados de exemplo
    # Você pode implementar um modelo de banco para entregas depois
    entregas_exemplo = [
        {
            "cliente": "João Silva",
            "apartamento": "201",
            "descricao": "Correspondência",
            "data_hora": "30/09/2025 14:30"
        },
        {
            "cliente": "Maria Santos",
            "apartamento": "105",
            "descricao": "Encomenda Amazon",
            "data_hora": "30/09/2025 10:15"
        },
        {
            "cliente": "Pedro Oliveira",
            "apartamento": "303",
            "descricao": "Medicamentos",
            "data_hora": "29/09/2025 16:45"
        }
    ]
    
    # Filtrar por cliente ou apartamento se fornecido
    if cliente:
        entregas_exemplo = [e for e in entregas_exemplo if cliente.lower() in e['cliente'].lower()]
    if apartamento:
        entregas_exemplo = [e for e in entregas_exemplo if apartamento in e['apartamento']]
    
    return jsonify(entregas_exemplo)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
