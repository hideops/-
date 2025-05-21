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
        show_friends=True,
        show_groups=True
    )


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))



def generate_social_graph_image_with_avatars(vk_api_instance, user_id):
    try:
        # Получаем информацию о пользователе и его друзьях
        user_info = vk_api_instance.users.get(user_ids=user_id, fields='photo_100,first_name,last_name')[0]
        friends = vk_api_instance.friends.get(user_id=user_id, fields='photo_100,first_name,last_name')['items']
    except Exception as e:
        print("Ошибка получения данных:", e)
        return None

    # Ограничиваем количество друзей для лучшей визуализации (например, 30)
    friends = friends[:30]

    # Создаем граф
    G = nx.Graph()

    # Добавляем центрального пользователя
    G.add_node(user_info['id'],
               photo=user_info.get('photo_100'),
               name=f"{user_info['first_name']} {user_info['last_name']}")

    # Добавляем друзей и связи с пользователем
    for friend in friends:
        friend_id = friend['id']
        G.add_node(friend_id,
                   photo=friend.get('photo_100'),
                   name=f"{friend['first_name']} {friend['last_name']}")
        G.add_edge(user_info['id'], friend_id)

    # Проверяем взаимные связи между друзьями
    #for i, friend1 in enumerate(friends):
        #for friend2 in friends[i + 1:]:
            #try:
                # Проверяем, являются ли friend1 и friend2 друзьями друг друга
                #are_friends = vk_api_instance.friends.areFriends(
                    #user_ids=friend1['id'],
                    #need_sign=0,
                    #target_uid=friend2['id']
                #)
                #if are_friends and are_friends[0].get('friend_status') == 3:  # 3 - взаимная дружба
                    #G.add_edge(friend1['id'], friend2['id'])
            #except Exception as e:
                #print(f"Ошибка при проверке связи между {friend1['id']} и {friend2['id']}: {e}")
                #continue

    # Визуализация графа
    plt.figure(figsize=(15, 12))
    pos = nx.spring_layout(G, k=0.3, seed=42)  # k - параметр расстояния между узлами

    # Рисуем связи
    nx.draw_networkx_edges(G, pos, alpha=0.5, width=1, edge_color='gray')

    # Рисуем узлы с аватарками
    ax = plt.gca()
    for node in G.nodes():
        photo_url = G.nodes[node].get('photo')
        if not photo_url:
            continue

        try:
            # Загружаем и обрабатываем аватарку
            response = requests.get(photo_url)
            img = Image.open(io.BytesIO(response.content)).resize((60, 60))

            # Делаем круглые аватарки
            mask = Image.new('L', (60, 60), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 60, 60), fill=255)
            img.putalpha(mask)

            imagebox = OffsetImage(img, zoom=1)
            ab = AnnotationBbox(imagebox, pos[node], frameon=False)
            ax.add_artist(ab)

            # Добавляем подпись с именем
            plt.text(pos[node][0], pos[node][1] - 0.1,
                     G.nodes[node]['name'],
                     fontsize=8,
                     ha='center',
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', boxstyle='round,pad=0.2'))
        except Exception as e:
            print(f"Ошибка при обработке аватарки для {node}: {e}")
            continue

    # Выделяем центрального пользователя
    if user_info['id'] in pos:
        plt.scatter(pos[user_info['id']][0], pos[user_info['id']][1],
                    s=2000, edgecolors='red', facecolors='none', linewidths=2)

    plt.title(f'Социальный граф {user_info["first_name"]} {user_info["last_name"]}\n(Взаимные связи друзей)',
              fontsize=14, pad=20)
    plt.axis('off')

    # Добавляем легенду
    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', label='Вы',
                   markerfacecolor='none', markersize=10, markeredgecolor='red', markeredgewidth=2),
        plt.Line2D([0], [0], marker='o', color='w', label='Друзья',
                   markerfacecolor='none', markersize=10, markeredgecolor='blue'),
        plt.Line2D([0], [0], color='gray', lw=1, label='Взаимные связи')
    ]
    plt.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1))

    # Сохраняем изображение
    img_io = io.BytesIO()
    plt.savefig(img_io, format='png', bbox_inches='tight', dpi=120)
    img_io.seek(0)
    encoded_img = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()

    return encoded_img





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


# 👇 сюда добавь свои остальные функции: create_interests_graph, create_post_activity_graph, create_groups_stats и т.д.
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

@app.route('/social_graph', methods=['GET', 'POST'])
def social_graph():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    graph_img = None

    if request.method == 'POST':
        vk_url = request.form['vk_url']
        vk_user_id = extract_user_id(vk_url)

        if not vk_user_id:
            flash('Невалидный VK URL', 'danger')
            return redirect(url_for('social_graph'))

        token = 'c63860bfc63860bfc63860bffbc508895bcc638c63860bfae23074c88948f64e3e66c9a'
        vk_api_instance = get_vk_api(token)

        try:
            graph_img = generate_social_graph_image_with_avatars(vk_api_instance, vk_user_id)
        except Exception as e:
            flash('Ошибка при построении графа связей', 'danger')
            return redirect(url_for('social_graph'))

    return render_template('social_graph.html', graph_img=graph_img)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
