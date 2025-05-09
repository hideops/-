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
            token = 'токен'  # Замените на ваш токен
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
                    total_groups_graph=total_groups_graph,  # График общего количества групп
                    top_groups_graph=top_groups_graph  # График топ-5 групп
                )
            except Exception as e:
                flash('Ошибка при получении данных', 'danger')
                return redirect(url_for('profile'))
        else:
            flash('Неверный формат URL', 'danger')
            return redirect(url_for('profile'))

    return render_template('profile.html')


def create_groups_activity_graph(groups_info, top_groups_info):
    # График общего количества групп
    if not groups_info:
        return None

    total_groups = groups_info.get('total', 0)

    # Создаем график для общего количества групп
    plt.figure(figsize=(5, 5))
    plt.bar(['Группы'], [total_groups], color='green')
    plt.title('Общее количество групп')

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    total_groups_graph = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()

    # График топ-5 групп по количеству участников
    if not top_groups_info:
        return total_groups_graph, None

    group_names = [g[0] for g in top_groups_info]
    group_members = [g[1] for g in top_groups_info]

    plt.figure(figsize=(8, 5))
    plt.bar(group_names, group_members, color='lightcoral')
    plt.xticks(rotation=45, ha='right')
    plt.title('Топ-5 групп по количеству участников')
    plt.xlabel('Группы')
    plt.ylabel('Количество участников')

    img_io = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    top_groups_graph = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()

    return total_groups_graph, top_groups_graph

# Функция для извлечения ID пользователя ВКонтакте из ссылки
def extract_user_id(url):
    if "vk.com/" in url:
        username = url.split("vk.com/")[1]
        token = 'токен'  # Замените на ваш токен
        vk_api_instance = get_vk_api(token)
        try:
            user_info = vk_api_instance.users.get(user_ids=username)
            return user_info[0]['id']
        except Exception as e:
            return None
    return None



# Логика выхода
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


# Функция для создания графиков интересов
def create_interests_graph(user_info):
    interests_str = user_info.get('interests', '')

    if not interests_str.strip():
        return None  # Нет интересов — график не строим

    # Разбиваем по запятым и убираем лишние пробелы
    interests = [i.strip() for i in interests_str.split(',') if i.strip()]

    if not interests:
        return None

    # Готовим данные для графика
    counts = {interest: 1 for interest in interests}

    plt.figure(figsize=(8, 4))
    plt.bar(counts.keys(), counts.values(), color='skyblue')
    plt.xticks(rotation=45, ha='right')
    plt.title('Интересы пользователя')
    plt.yticks([])

    img_io = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    graph_data = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()

    return graph_data

def create_post_activity_graph(vk_api_instance, vk_user_id):
    try:
        posts = vk_api_instance.wall.get(owner_id=vk_user_id, count=100)['items']
    except Exception:
        return None

    if not posts:
        return None

    month_counts = {i: 0 for i in range(1, 13)}
    for post in posts:
        timestamp = post['date']
        month = time.localtime(timestamp).tm_mon
        month_counts[month] += 1

    months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
              'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    post_values = [month_counts[i] for i in range(1, 13)]

    plt.figure(figsize=(10, 5))
    plt.bar(months, post_values, color='orange')
    plt.xticks(rotation=45)
    plt.title('Активность публикаций по месяцам')
    plt.ylabel('Количество публикаций')
    plt.tight_layout()

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    graph_data = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()

    return graph_data

def create_gender_stats(vk_api_instance, vk_user_id):
    try:
        friends_data = vk_api_instance.friends.get(user_id=vk_user_id, fields='sex')
    except Exception:
        return None, None

    male_count = 0
    female_count = 0

    for friend in friends_data['items']:
        sex = friend.get('sex')
        if sex == 1:
            female_count += 1
        elif sex == 2:
            male_count += 1

    gender_counts = {'Мужчины': male_count, 'Женщины': female_count}

    return gender_counts


def create_groups_stats(vk_api_instance, vk_user_id):
    try:
        groups_data = vk_api_instance.groups.get(user_id=vk_user_id, extended=1, fields='members_count')
    except Exception:
        return None, None, None, None

    groups_info = {'total': len(groups_data['items'])}

    # Сортируем группы по количеству участников
    top_groups = sorted(groups_data['items'], key=lambda g: g.get('members_count', 0), reverse=True)[:5]
    top_groups_info = [(g['name'], g.get('members_count', 0)) for g in top_groups]

    # Создаем графики
    total_groups_graph, top_groups_graph = create_groups_activity_graph(groups_info, top_groups_info)

    return groups_info, top_groups_info, total_groups_graph, top_groups_graph




def create_friends_stats(vk_api_instance, vk_user_id):
    try:
        friends_data = vk_api_instance.friends.get(user_id=vk_user_id, fields='sex')
    except Exception:
        return None, None, None

    male_count = 0
    female_count = 0

    for friend in friends_data['items']:
        sex = friend.get('sex')
        if sex == 1:
            female_count += 1
        elif sex == 2:
            male_count += 1

    gender_counts = {'Мужчины': male_count, 'Женщины': female_count}

    # Создаем график для статистики по полу друзей
    gender_graph = create_friends_gender_graph(gender_counts)

    return gender_counts, friends_data, gender_graph


def create_friends_gender_graph(gender_counts):
    if not gender_counts:
        return None

    # Создаем график
    labels = list(gender_counts.keys())
    values = list(gender_counts.values())

    plt.figure(figsize=(5, 5))
    plt.pie(values, labels=labels, autopct='%1.1f%%', colors=['#ff9999','#66b3ff'])
    plt.title('Статистика по полу друзей')

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    graph_data = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()
    return graph_data

def create_groups_activity_graph(groups_info, top_groups_info):
    # График общего количества групп
    if not groups_info:
        return None

    total_groups = groups_info.get('total', 0)

    # Создаем график для общего количества групп
    plt.figure(figsize=(5, 5))
    plt.bar(['Группы'], [total_groups], color='green')
    plt.title('Общее количество групп')

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    total_groups_graph = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()

    # График топ-5 групп по количеству участников
    if not top_groups_info:
        return total_groups_graph, None

    group_names = [g[0] for g in top_groups_info]
    group_members = [g[1] for g in top_groups_info]

    plt.figure(figsize=(8, 5))
    plt.bar(group_names, group_members, color='lightcoral')
    plt.xticks(rotation=45, ha='right')
    plt.title('Топ-5 групп по количеству участников')
    plt.xlabel('Группы')
    plt.ylabel('Количество участников')

    img_io = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    top_groups_graph = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()

    return total_groups_graph, top_groups_graph
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
