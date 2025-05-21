from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import vk_api
import io
import base64
import time
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import requests
import traceback
from PIL import Image, ImageDraw

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


def get_vk_api(token):
    vk_session = vk_api.VkApi(token=token)
    return vk_session.get_api()


@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('profile'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        new_user = User(username=username, password=hashed_password)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('Ошибка регистрации!', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Вы вошли!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Неверный логин или пароль', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


def extract_user_id(url_or_id):
    token = 'c63860bfc63860bfc63860bffbc508895bcc638c63860bfae23074c88948f64e3e66c9a'
    vk_api_instance = get_vk_api(token)

    if "vk.com/" in url_or_id:
        username = url_or_id.split("vk.com/")[1].strip('/')
    else:
        username = url_or_id.strip('/')

    try:
        user_info = vk_api_instance.users.get(user_ids=username)
        return user_info[0]['id']
    except Exception as e:
        print("Ошибка при извлечении ID:", e)
        return None


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

        scale = request.form.get('scale', '1')
        color = request.form.get('color', 'blue')

        show_interests = 'show_interests' in request.form
        show_posts = 'show_posts' in request.form
        show_friends = 'show_friends' in request.form
        show_groups = 'show_groups' in request.form

        if vk_user_id:
            token = 'c63860bfc63860bfc63860bffbc508895bcc638c63860bfae23074c88948f64e3e66c9a'
            vk_api_instance = get_vk_api(token)

            try:
                user_info = vk_api_instance.users.get(
                    user_ids=vk_user_id,
                    fields='sex,bdate,interests,city'
                )[0]

                formatted_bdate = format_bdate(user_info.get('bdate', ''))

                interests_graph = create_interests_graph(user_info) if show_interests else None
                post_activity_graph = create_post_activity_graph(vk_api_instance, vk_user_id) if show_posts else None
                friends_gender_stats, friends_data, friends_gender_graph = create_friends_stats(vk_api_instance, vk_user_id) if show_friends else (None, None, None)
                groups_info, top_groups_info, total_groups_graph, top_groups_graph = create_groups_stats(vk_api_instance, vk_user_id) if show_groups else (None, None, None, None)

                # 🔥 исправлено: корректный вызов генерации графа
                social_graph_img = generate_social_graph_image_with_avatars(vk_api_instance, vk_user_id)

                return render_template('profile.html',
                    user_info=user_info,
                    formatted_bdate=formatted_bdate,
                    interests_graph=interests_graph,
                    post_activity_graph=post_activity_graph,
                    friends_gender_stats=friends_gender_stats,
                    friends_data=friends_data,
                    friends_gender_graph=friends_gender_graph,
                    groups_info=groups_info,
                    top_groups_info=top_groups_info,
                    total_groups_graph=total_groups_graph,
                    top_groups_graph=top_groups_graph,
                    scale=scale,
                    color=color,
                    show_interests=show_interests,
                    show_posts=show_posts,
                    show_friends=show_friends,
                    show_groups=show_groups,
                    social_graph_img=social_graph_img
                )
            except Exception as e:
                print("Ошибка при обработке профиля:", e)
                traceback.print_exc()
                flash('Ошибка при получении данных', 'danger')
                return redirect(url_for('profile'))
        else:
            flash('Неверный формат ссылки или ID', 'danger')
            return redirect(url_for('profile'))

    return render_template('profile.html',
        scale='1',
        color='blue',
        show_interests=True,
        show_posts=True,
