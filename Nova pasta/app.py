from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os
import json

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
    perfil = db.Column(db.String(20), default='usuario', nullable=False)  # 'admin' ou 'usuario'
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)
    
    def set_password(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.senha_hash, senha)
    
    def is_admin(self):
        return self.perfil == 'admin'
    
    def agendamentos_esta_semana(self):
        """Conta quantos agendamentos o usuário fez nesta semana"""
        hoje = datetime.now().date()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        fim_semana = inicio_semana + timedelta(days=6)
        
        return Agendamento.query.filter(
            Agendamento.usuario_id == self.id,
            Agendamento.data >= inicio_semana.strftime('%Y-%m-%d'),
            Agendamento.data <= fim_semana.strftime('%Y-%m-%d')
        ).count()
    
    def pode_agendar(self):
        """Verifica se o usuário pode fazer mais agendamentos esta semana"""
        if self.is_admin():
            return True
        return self.agendamentos_esta_semana() < 1

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
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    # Relacionamento com usuário
    usuario = db.relationship('Usuario', backref=db.backref('agendamentos', lazy=True))

class Entrega(db.Model):
    __tablename__ = 'entregas'
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(120), nullable=False)
    apartamento = db.Column(db.String(20), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    data_recebimento = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pendente')  # 'pendente', 'entregue', 'devolvida'
    observacoes = db.Column(db.Text)
    usuario_cadastro_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)  # Mudado para nullable=True
    data_entrega = db.Column(db.DateTime)
    
    # Relacionamentos
    usuario_cadastro = db.relationship('Usuario', backref=db.backref('entregas_cadastradas', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'cliente': self.cliente,
            'apartamento': self.apartamento,
            'descricao': self.descricao,
            'data_recebimento': self.data_recebimento.strftime('%d/%m/%Y %H:%M') if self.data_recebimento else '',
            'status': self.status,
            'observacoes': self.observacoes or '',
            'data_entrega': self.data_entrega.strftime('%d/%m/%Y %H:%M') if self.data_entrega else '',
            'usuario_cadastro': self.usuario_cadastro.nome if self.usuario_cadastro else 'Sistema'
        }

# ==========================
# DECORADORES DE PERMISSÃO
# ==========================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({"erro": "Acesso negado. Apenas administradores."}), 403
        return f(*args, **kwargs)
    return decorated_function

def check_weekly_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"erro": "Login necessário"}), 401
        
        if not current_user.pode_agendar():
            return jsonify({
                "erro": "Limite semanal atingido. Usuários podem agendar apenas 1 horário por semana."
            }), 429
        
        return f(*args, **kwargs)
    return decorated_function

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
            'email': current_user.email,
            'is_admin': current_user.is_admin(),
            'perfil': current_user.perfil,
            'agendamentos_semana': current_user.agendamentos_esta_semana(),
            'pode_agendar': current_user.pode_agendar()
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
@check_weekly_limit
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
            horario=horario,
            usuario_id=current_user.id  # Associa ao usuário logado
        )
        db.session.add(novo_agendamento)
        db.session.commit()

        agendamentos_semana = current_user.agendamentos_esta_semana()
        limite_msg = ""
        if not current_user.is_admin() and agendamentos_semana >= 1:
            limite_msg = f" (Limite semanal: {agendamentos_semana}/1)"

        return jsonify({"mensagem": f"Agendamento realizado{limite_msg}"}), 200
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
            return jsonify({"erro": "Dados incompletos"}), 400

        # Busca o agendamento
        agendamento = Agendamento.query.filter(
            db.func.lower(Agendamento.nome) == nome.lower(),
            Agendamento.apto == apto,
            Agendamento.data == data,
            Agendamento.horario == horario
        ).first()
        
        if not agendamento:
            return jsonify({"erro": "Agendamento não encontrado"}), 404
        
        # Verifica se o usuário pode remover (próprio agendamento ou admin)
        if not current_user.is_admin() and agendamento.usuario_id != current_user.id:
            return jsonify({"erro": "Você só pode remover seus próprios agendamentos"}), 403
        
        db.session.delete(agendamento)
        db.session.commit()

        return jsonify({"mensagem": "Agendamento removido com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": f"Erro ao remover agendamento: {str(e)}"}), 500

@app.route('/verificar_limite')
@login_required
def verificar_limite():
    return jsonify({
        'pode_agendar': current_user.pode_agendar(),
        'is_admin': current_user.is_admin(),
        'agendamentos_semana': current_user.agendamentos_esta_semana(),
        'perfil': current_user.perfil
    })

@app.route('/entregas')
@login_required
def entregas():
    user_data = {
        'nome': current_user.nome,
        'email': current_user.email,
        'is_admin': current_user.is_admin(),
        'perfil': current_user.perfil
    }
    return render_template('entregas.html', user=user_data)

# ==========================
# ROTAS DE ENTREGAS
# ==========================
@app.route('/consultar_entregas', methods=['GET'])
@login_required
def consultar_entregas():
    try:
        cliente = request.args.get('cliente', '').strip()
        apartamento = request.args.get('apartamento', '').strip()
        status = request.args.get('status', '').strip()
        
        query = Entrega.query
        
        if cliente:
            query = query.filter(db.func.lower(Entrega.cliente).like(f"%{cliente.lower()}%"))
        if apartamento:
            query = query.filter(Entrega.apartamento.like(f"%{apartamento}%"))
        if status:
            query = query.filter(Entrega.status == status)
        
        entregas = query.order_by(Entrega.data_recebimento.desc()).all()
        
        return jsonify([entrega.to_dict() for entrega in entregas])
    except Exception as e:
        print(f"Erro ao consultar entregas: {e}")
        # Retorna uma lista vazia em caso de erro
        return jsonify([])

@app.route('/cadastrar_entrega', methods=['POST'])
@login_required
@admin_required
def cadastrar_entrega():
    try:
        dados = request.form
        cliente = dados.get('cliente')
        apartamento = dados.get('apartamento')
        descricao = dados.get('descricao')
        observacoes = dados.get('observacoes', '')
        
        if not cliente or not apartamento or not descricao:
            return jsonify({"erro": "Cliente, apartamento e descrição são obrigatórios"}), 400
        
        nova_entrega = Entrega(
            cliente=cliente,
            apartamento=apartamento,
            descricao=descricao,
            observacoes=observacoes,
            usuario_cadastro_id=current_user.id
        )
        
        db.session.add(nova_entrega)
        db.session.commit()
        
        return jsonify({"mensagem": "Entrega cadastrada com sucesso!", "entrega": nova_entrega.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": f"Erro ao cadastrar entrega: {str(e)}"}), 500

@app.route('/atualizar_status_entrega', methods=['POST'])
@login_required
@admin_required
def atualizar_status_entrega():
    try:
        dados = request.form
        entrega_id = dados.get('entrega_id')
        novo_status = dados.get('status')
        
        if not entrega_id or not novo_status:
            return jsonify({"erro": "ID da entrega e status são obrigatórios"}), 400
        
        if novo_status not in ['pendente', 'entregue', 'devolvida']:
            return jsonify({"erro": "Status inválido"}), 400
        
        entrega = Entrega.query.get(entrega_id)
        if not entrega:
            return jsonify({"erro": "Entrega não encontrada"}), 404
        
        entrega.status = novo_status
        if novo_status == 'entregue':
            entrega.data_entrega = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({"mensagem": "Status atualizado com sucesso!", "entrega": entrega.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": f"Erro ao atualizar status: {str(e)}"}), 500

@app.route('/excluir_entrega', methods=['POST'])
@login_required
@admin_required
def excluir_entrega():
    try:
        entrega_id = request.form.get('entrega_id')
        
        if not entrega_id:
            return jsonify({"erro": "ID da entrega é obrigatório"}), 400
        
        entrega = Entrega.query.get(entrega_id)
        if not entrega:
            return jsonify({"erro": "Entrega não encontrada"}), 404
        
        db.session.delete(entrega)
        db.session.commit()
        
        return jsonify({"mensagem": "Entrega excluída com sucesso!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": f"Erro ao excluir entrega: {str(e)}"}), 500

# ==========================
# ROTAS DE ADMINISTRAÇÃO
# ==========================
@app.route('/admin/usuarios')
@login_required
@admin_required
def gerenciar_usuarios():
    usuarios = Usuario.query.all()
    return render_template('admin_usuarios.html', usuarios=usuarios, user={
        'nome': current_user.nome,
        'email': current_user.email,
        'is_admin': current_user.is_admin()
    })

@app.route('/admin/promover_usuario', methods=['POST'])
@login_required
@admin_required
def promover_usuario():
    try:
        user_id = request.form.get('user_id')
        novo_perfil = request.form.get('perfil')  # 'admin' ou 'usuario'
        
        if novo_perfil not in ['admin', 'usuario']:
            return jsonify({"erro": "Perfil inválido"}), 400
        
        usuario = Usuario.query.get(user_id)
        if not usuario:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        usuario.perfil = novo_perfil
        db.session.commit()
        
        return jsonify({"mensagem": f"Usuário {usuario.nome} agora é {novo_perfil}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

@app.route('/meu_perfil')
@login_required
def meu_perfil():
    agendamentos_usuario = Agendamento.query.filter_by(usuario_id=current_user.id).all()
    agendamentos_semana = current_user.agendamentos_esta_semana()
    
    return render_template('perfil.html', 
                         user={
                             'nome': current_user.nome,
                             'email': current_user.email,
                             'is_admin': current_user.is_admin(),
                             'perfil': current_user.perfil,
                             'agendamentos_semana': agendamentos_semana
                         },
                         agendamentos=agendamentos_usuario)

# ==========================
# FUNÇÕES UTILITÁRIAS
# ==========================
def criar_admin_inicial():
    """Cria o primeiro usuário admin se não existir"""
    try:
        # Tenta encontrar um admin pelo email primeiro
        admin_existente = Usuario.query.filter_by(email='admin@hotel.com').first()
        if not admin_existente:
            admin = Usuario(
                nome='Administrador',
                email='admin@hotel.com',
                perfil='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuário admin criado - Email: admin@hotel.com, Senha: admin123")
        else:
            print("✅ Usuário admin já existe")
    except Exception as e:
        print(f"❌ Erro ao verificar/criar admin: {e}")
        # Cria as tabelas novamente se houver erro
        try:
            db.drop_all()
            db.create_all()
            admin = Usuario(
                nome='Administrador',
                email='admin@hotel.com',
                perfil='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Banco recriado e admin criado!")
        except Exception as e2:
            print(f"❌ Erro crítico: {e2}")

# ==========================
# INICIALIZAÇÃO DO APP
# ==========================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        criar_admin_inicial()
    print("🚀 Servidor iniciando...")
    app.run(host='0.0.0.0', port=5000, debug=True)
