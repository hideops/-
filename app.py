from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import vk_api
import matplotlib.pyplot as plt
import io
import base64
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Замените на свой секретный ключ
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)


# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


# Авторизация через API ВКонтакте
def get_vk_api(token):
    vk_session = vk_api.VkApi(token=token)
    return vk_session.get_api()


# Главная страница
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')


# Страница регистрации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = User(username=username, password=hashed_password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Регистрация прошла успешно!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Ошибка при регистрации!', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')


# Страница входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


# Функция для форматирования даты рождения
def format_bdate(bdate_str):
    from datetime import datetime

    try:
        date = datetime.strptime(bdate_str, "%d.%m.%Y")
    except ValueError:
        try:
            date = datetime.strptime(bdate_str, "%d.%m")
        except ValueError:
            return 'Не указана'

    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    return f"{date.day} {months[date.month - 1]}"

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        vk_url = request.form['vk_url']
        vk_user_id = extract_user_id(vk_url)

        if vk_user_id:
            token = 'c63860bfc63860bfc63860bffbc508895bcc638c63860bfae23074c88948f64e3e66c9a'  # Замените на ваш токен
            vk_api_instance = get_vk_api(token)

            try:
                user_info = vk_api_instance.users.get(
                    user_ids=vk_user_id,
                    fields='sex,bdate,interests,city'
                )
                user = user_info[0]

                formatted_bdate = format_bdate(user.get('bdate', ''))
                interests_graph = create_interests_graph(user)
                post_activity_graph = create_post_activity_graph(vk_api_instance, vk_user_id)

                # Получаем данные о друзьях и группах
                friends_gender_stats, friends_data, friends_gender_graph = create_friends_stats(vk_api_instance, vk_user_id)
                groups_info, top_groups_info, total_groups_graph, top_groups_graph = create_groups_stats(vk_api_instance, vk_user_id)

                return render_template(
                    'profile.html',
                    user_info=user,
                    interests_graph=interests_graph,
                    post_activity_graph=post_activity_graph,
                    formatted_bdate=formatted_bdate,
                    friends_gender_stats=friends_gender_stats,
                    friends_data=friends_data,  # Вы можете использовать friends_data для дополнительной информации
                    groups_info=groups_info,
                    top_groups_info=top_groups_info,
                    friends_gender_graph=friends_gender_graph,  # График друзей
