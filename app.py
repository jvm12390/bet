from flask import Flask, render_template, redirect, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.message import EmailMessage
import random

# Configura con tu correo real
EMAIL_ADDRESS = 'hascompradotunumero@gmail.com'
EMAIL_PASSWORD = 'zrtr vzus wgie nacf'  # O una clave de app de Gmail


app = Flask(__name__)
app.secret_key = 'clave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///apuesta_club.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    balance = db.Column(db.Integer, default=0)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(4))  # Código de 4 dígitos


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)
    initial_balance = db.Column(db.Integer, default=10000)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pendiente')
    participants = db.relationship('BetParticipant', backref='bet', lazy=True)
    ganador_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class BetParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bet_id = db.Column(db.Integer, db.ForeignKey('bet.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Integer, default=0)
    odds = db.Column(db.Float, default=1.5)

    user = db.relationship('User', foreign_keys=[user_id])

def enviar_codigo_verificacion(destinatario, codigo):
    msg = EmailMessage()
    msg['Subject'] = 'Tu código de verificación - BadBro'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = destinatario
    msg.set_content(f'Tu código de verificación es: {codigo}')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)


@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return render_template('dashboard.html', user=user)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        # Comprobar si el email o el nombre de usuario ya están en uso
        if User.query.filter_by(username=username).first():
            return "Ese nombre de usuario ya está en uso."
        if User.query.filter_by(email=email).first():
            return "Ese correo ya está registrado."

        # Generar código de verificación de 4 dígitos
        codigo = str(random.randint(1000, 9999))

        # Crear usuario sin verificar
        user = User(
            email=email,
            username=username,
            password=password,
            balance=0,
            is_verified=False,
            verification_code=codigo
        )
        db.session.add(user)
        db.session.commit()

        # Enviar código de verificación al correo
        enviar_codigo_verificacion(email, codigo)

        # Guardar ID del usuario pendiente en la sesión
        session['pending_user_id'] = user.id

        return redirect(url_for('verificar'))

    return render_template('register.html')



class UserBet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    bet_id = db.Column(db.Integer, db.ForeignKey('bet.id'))
    selected_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Integer, nullable=False)
    odds = db.Column(db.Float, nullable=False)

    bet = db.relationship('Bet', foreign_keys=[bet_id])
    selected_user = db.relationship('User', foreign_keys=[selected_user_id])



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            if not user.is_verified:
                return "Tu cuenta aún no ha sido verificada. Revisa tu correo."
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))

        return "Usuario o contraseña incorrectos."

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        invite_code = request.form['invite_code']
        initial_balance = int(request.form['initial_balance'])

        group = Group(name=name, invite_code=invite_code, initial_balance=initial_balance, admin_id=session['user_id'])
        db.session.add(group)
        db.session.commit()

        user = User.query.get(session['user_id'])
        user.group_id = group.id
        user.balance = initial_balance
        db.session.commit()

        return redirect(url_for('index'))

    return render_template('create_group.html')

@app.route('/join_group', methods=['GET', 'POST'])
def join_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        invite_code = request.form['invite_code']
        group = Group.query.filter_by(invite_code=invite_code).first()
        if group:
            user = User.query.get(session['user_id'])
            user.group_id = group.id
            user.balance = group.initial_balance
            db.session.commit()
            return redirect(url_for('index'))

    return render_template('join_group.html')


@app.route('/create_bet', methods=['GET', 'POST'])
def create_bet():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user.group_id:
        return "Debes estar en un grupo para crear apuestas."

    group_users = User.query.filter_by(group_id=user.group_id).all()

    if request.method == 'POST':
            title = request.form['title']
            participants_ids = request.form.getlist('participants')

            bet = Bet(title=title, group_id=user.group_id, creator_id=user.id)
            db.session.add(bet)
            db.session.commit()

            for pid in participants_ids:
                participant = BetParticipant(bet_id=bet.id, user_id=int(pid), amount=0, odds=1.5)
                db.session.add(participant)
                db.session.commit()

            return redirect(url_for('index'))

    return render_template('create_bet.html', group_users=group_users)

@app.route('/apuestas', methods=['GET', 'POST'])
def apuestas():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    group = user.group

    if request.method == 'POST':
        bet_id = request.form.get('bet_id')
        selected_user_id = request.form.get('selected_user_id')
        amount = request.form.get('amount')

        # Validaciones
        if not selected_user_id:
            return "Debes seleccionar un participante antes de apostar."

        if not amount or not amount.isdigit():
            return "Debes ingresar una cantidad válida."

        amount = int(amount)

        if amount > user.balance:
            return "No tienes suficiente saldo para esta apuesta."

        bet = Bet.query.get(bet_id)

        if not bet or bet.status != 'pendiente':
            return "Apuesta no válida."

        selected = BetParticipant.query.filter_by(bet_id=bet.id, user_id=selected_user_id).first()

        if not selected:
            return "El participante seleccionado no forma parte de esta apuesta."

        # Guardar la apuesta del usuario
        user_bet = UserBet(
            user_id=user.id,
            bet_id=bet.id,
            selected_user_id=selected_user_id,
            amount=amount,
            odds=selected.odds
        )

        user.balance -= amount
        db.session.add(user_bet)
        db.session.commit()

        return redirect(url_for('mis_apuestas'))

    # Mostrar apuestas disponibles del grupo del usuario
    if group:
        bets = Bet.query.filter_by(group_id=group.id, status='pendiente').all()
    else:
        bets = []

    return render_template('apuestas.html', bets=bets, user=user)


@app.route('/mis_apuestas')
def mis_apuestas():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    # Obtener todas las apuestas realizadas por el usuario
    user_bets = UserBet.query.filter_by(user_id=user.id).all()

    return render_template('mis_apuestas.html', user_bets=user_bets)




@app.route('/clasificacion')
def clasificacion():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user.group_id:
        return "No perteneces a ningún grupo."

    miembros = User.query.filter_by(group_id=user.group_id).order_by(User.balance.desc()).all()

    return render_template('clasificacion.html', miembros=miembros)
@app.route('/verificar', methods=['GET', 'POST'])
def verificar():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get(user_id)

    if request.method == 'POST':
        codigo_ingresado = request.form['codigo']
        if user.verification_code == codigo_ingresado:
            user.is_verified = True
            user.verification_code = None
            db.session.commit()
            session.pop('pending_user_id', None)
            return redirect(url_for('login'))
        else:
            return "Código incorrecto. Intenta de nuevo."

    return render_template('verificar.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', user=user)


@app.route('/resolver_apuesta/<int:bet_id>', methods=['GET', 'POST'])
def resolver_apuesta(bet_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    bet = Bet.query.get_or_404(bet_id)

    if bet.status != 'pendiente':
        return "Esta apuesta ya fue resuelta."

    participantes = BetParticipant.query.filter_by(bet_id=bet.id).all()

    if request.method == 'POST':
        ganador_id = int(request.form['ganador_id'])
        bet.status = 'resuelta'
        bet.ganador_id = ganador_id

        # Procesar apuestas ganadoras
        apuestas = UserBet.query.filter_by(bet_id=bet.id).all()
        for apuesta in apuestas:
            if apuesta.selected_user_id == ganador_id:
                ganancia = apuesta.amount * apuesta.odds
                apuesta.user.balance += ganancia

        db.session.commit()
        return redirect(url_for('apuestas'))

    return render_template('resolver_apuesta.html', bet=bet, participantes=participantes)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
