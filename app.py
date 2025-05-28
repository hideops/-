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
from PIL import Image, ImageDraw
import requests
import traceback
from gigachat import GigaChat
from gigachat.models import Chat, Messages
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from requests.exceptions import RequestException
import vk_api.exceptions



app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)



giga = GigaChat(
    credentials="Njk5NGJmNzktZTk4NC00YTNjLWI1YjctNGVlY2E3YTlkNzIyOmI0MjI2MTI2LTY0Y2UtNGU0MS04NmU3LWZjNzVlMDExOTc2Mw==",
    verify_ssl_certs=False,
    timeout=10  
)



def get_vk_api(token):
    vk_session = vk_api.VkApi(token=token)
    return vk_session.get_api()


def extract_user_id(url_or_id):
    if "vk.com/" in url_or_id:
        username = url_or_id.split("vk.com/")[1].strip('/')
    else:
        username = url_or_id.strip('/')

    try:
        token = 'vk1.a.USGB6XBqseXr9H8xXVtGRoQnwcM7veA31BKJFw1r-hH7SO1PbvGUrk4cCP3I5nOvVvKld8T_tLnZO3oQyGAWzVXxAQHTNo3Af6pFWqB8ICAvocx9O_WMOVhznB1FZEdsVULvpWidm8UNfOr9Efsw2FWczIDPUunEilRgWyB_4bhcVNgw05g7I-orFhF78rps5VlsQIJlomGgrJSGeUIqGw'
        vk_api_instance = get_vk_api(token)
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


def create_interests_graph(user_info):
    interests_str = user_info.get('interests', '')
    interests = [i.strip() for i in interests_str.split(',') if i.strip()]

    if not interests:
        return None

    plt.figure(figsize=(8, 4))
    plt.bar(interests, [1] * len(interests), color='skyblue')
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
        month = time.localtime(post['date']).tm_mon
        month_counts[month] += 1

    months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
    plt.figure(figsize=(10, 5))
    plt.bar(months, [month_counts[i] for i in range(1, 13)], color='orange')
    plt.title('Активность публикаций')
    plt.ylabel('Количество')
    plt.tight_layout()

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    graph_data = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()
    return graph_data


def create_friends_stats(vk_api_instance, vk_user_id):
    try:
        friends_data = vk_api_instance.friends.get(user_id=vk_user_id, fields='sex', count=1000)
        time.sleep(0.4)
    except Exception:
        return None, None, None

    male = sum(1 for f in friends_data['items'] if f.get('sex') == 2)
    female = sum(1 for f in friends_data['items'] if f.get('sex') == 1)

    plt.figure(figsize=(5, 5))
    plt.pie([male, female], labels=['Мужчины', 'Женщины'], autopct='%1.1f%%', colors=['#66b3ff', '#ff9999'])
    plt.title('Друзья по полу')

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    graph_data = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()
    return {'Мужчины': male, 'Женщины': female}, friends_data, graph_data


def create_groups_stats(vk_api_instance, vk_user_id):
    try:
        groups_data = vk_api_instance.groups.get(user_id=vk_user_id, extended=1, fields='members_count', count=100)
    except Exception:
        return None, None, None, None


    groups_info = {'total': len(groups_data['items'])}

  
    top_groups = sorted(groups_data['items'], key=lambda g: g.get('members_count', 0), reverse=True)[:5]
    top_groups_info = [(g['name'], g.get('members_count', 0)) for g in top_groups]
   
    total_graph = create_total_groups_graph(groups_info['total'])
    top_graph = create_top_groups_graph(top_groups_info) if top_groups_info else None

    return groups_info, top_groups_info, total_graph, top_graph


def create_total_groups_graph(total):
    plt.figure(figsize=(5, 5))
    plt.bar(['Группы'], [total], color='green')
    plt.title('Всего групп')

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    graph_data = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()
    return graph_data


def create_top_groups_graph(groups):
    names = [g[0][:20] + '...' if len(g[0]) > 20 else g[0] for g in groups]
    counts = [g[1] for g in groups]

    plt.figure(figsize=(10, 5))
    plt.barh(names, counts, color='lightcoral')
    plt.title('Топ групп по участникам')
    plt.tight_layout()

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)
    graph_data = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()
    return graph_data


def generate_social_graph_image_with_avatars(vk_api_instance, user_id):
    try:
        
        user_info = vk_api_instance.users.get(user_ids=user_id, fields='photo_100,first_name,last_name')[0]
        friends = vk_api_instance.friends.get(user_id=user_id, fields='photo_100,first_name,last_name', count=50)[
            'items']
        time.sleep(0.4)
    except Exception:
        return None


    G = nx.Graph()
    G.add_node(user_info['id'],
               photo=user_info.get('photo_100'),
               name=f"{user_info['first_name']} {user_info['last_name']}")

    for friend in friends[:30]:  
        G.add_node(friend['id'],
                   photo=friend.get('photo_100'),
                   name=f"{friend['first_name']} {friend['last_name']}")
        G.add_edge(user_info['id'], friend['id'])


    plt.figure(figsize=(12, 10))
    pos = nx.spring_layout(G, k=0.3, seed=42)
    ax = plt.gca()


    nx.draw_networkx_edges(G, pos, alpha=0.3, width=1, edge_color='gray')


    for node in G.nodes():
        photo = G.nodes[node].get('photo')
        if not photo:
            continue

        try:
            response = requests.get(photo, timeout=5)
            img = Image.open(io.BytesIO(response.content)).resize((50, 50))


            mask = Image.new('L', (50, 50), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 50, 50), fill=255)
            img.putalpha(mask)

            imagebox = OffsetImage(img, zoom=1)
            ab = AnnotationBbox(imagebox, pos[node], frameon=False)
            ax.add_artist(ab)


            plt.text(pos[node][0], pos[node][1] - 0.08,
                     G.nodes[node]['name'],
                     fontsize=7,
                     ha='center',
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', boxstyle='round,pad=0.1'))
        except Exception:
            continue


    plt.scatter(pos[user_info['id']][0], pos[user_info['id']][1],
                s=1500, edgecolors='red', facecolors='none', linewidths=2)

    plt.title(f'Социальный граф {user_info["first_name"]} {user_info["last_name"]}', fontsize=14)
    plt.axis('off')


    img_io = io.BytesIO()
    plt.savefig(img_io, format='png', bbox_inches='tight', dpi=100)
    img_io.seek(0)
    encoded_img = base64.b64encode(img_io.getvalue()).decode('utf-8')
    plt.close()

    return encoded_img


def find_potential_connections(vk_api_instance, user_id, user_info):
    try:

        friends = vk_api_instance.friends.get(user_id=user_id, fields="interests,groups", count=100)["items"]
        time.sleep(0.4)
        candidates = []


        for friend in friends[:5]:
            try:
                fof = vk_api_instance.friends.get(user_id=friend["id"], fields="interests,groups", count=100)["items"]
                time.sleep(0.4)
                candidates.extend(
                    f for f in fof if f["id"] not in [x["id"] for x in friends] and not f.get("is_closed", True))
            except Exception:
                continue


        user_interests = set(user_info.get("interests", "").lower().split(", "))
        user_groups = set(str(g) for g in user_info.get("groups", []))

        filtered = []
        for person in candidates[:100]: 
            common = 0


            person_interests = set(person.get("interests", "").lower().split(", "))
            common += len(user_interests & person_interests)


            person_groups = set(str(g) for g in person.get("groups", []))
            common += len(user_groups & person_groups)

            if common > 0:
                person["match_score"] = common
                filtered.append(person)

        return sorted(filtered, key=lambda x: x.get("match_score", 0), reverse=True)[:10]
    except Exception:
        return []


def generate_dating_recommendations(vk_api_instance, user_info, candidates):
    if not candidates:
        return []

    recommendations = []
    base_url = "https://vk.com/id"

    for person in candidates[:5]:
        reason = "Друг друзей"  # По умолчанию
        photo = person.get("photo_100", "")

        # Формируем причину рекомендации
        if person.get("match_score", 0) > 0:
            reason = f"Совпадений: {person['match_score']}"

        recommendations.append({
            "name": f"{person.get('first_name', '')} {person.get('last_name', '')}",
            "url": f"{base_url}{person['id']}",
            "photo": photo,
            "reason": reason
        })

    return recommendations


MAT_WORDS = ["пиздец", "хуя", "блядь", "ебать", "ебал"]

def find_toxic_posts(vk_api_instance, vk_user_id):
    try:
        response = vk_api_instance.wall.get(owner_id=vk_user_id, count=100)
        posts = response.get('items', [])
    except Exception as e:
        print(f"Ошибка VK API: {e}")
        posts = []

    toxic_posts = []
    for post in posts:
        text = post.get('text', '').lower()
        if any(bad_word in text for bad_word in MAT_WORDS):
            post_id = post['id']
            owner_id = post['owner_id']
            url = f"https://vk.com/wall{owner_id}_{post_id}"
            toxic_posts.append({'text': post.get('text', '')[:100], 'url': url})

    return toxic_posts



def generate_user_analytics(user_info, friends_data, groups_info, top_groups_info):
    if not any([friends_data, groups_info]):
        return None

    prompt = f"""
    Проанализируй данные пользователя ВКонтакте и составь краткую аналитику (3-5 предложений).
    Имя: {user_info.get('first_name', 'Пользователь')} {user_info.get('last_name', '')}
    Интересы: {user_info.get('interests', 'не указаны')}
    Город: {user_info.get('city', {}).get('title', 'не указан')}
    Пол: {'женский' if user_info.get('sex') == 1 else 'мужской'}
    Друзей: {len(friends_data['items']) if friends_data else 0}
    Групп: {groups_info.get('total', 0) if groups_info else 0}
    Топ-3 группы: {', '.join([g[0] for g in top_groups_info[:3]]) if top_groups_info else 'не указаны'}

    Аналитика должна быть краткой, информативной и дружелюбной.
    """

    try:
        response = giga.chat(Chat(messages=[Messages(role="user", content=prompt)]))
        return response.choices[0].message.content
    except Exception:
        return "Не удалось сгенерировать аналитику."



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

        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('Ошибка регистрации', 'danger')
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
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


def load_user_data(vk_user_id, show_interests, show_posts, show_friends, show_groups, show_toxicity):
    token = 'vk1.a.USGB6XBqseXr9H8xXVtGRoQnwcM7veA31BKJFw1r-hH7SO1PbvGUrk4cCP3I5nOvVvKld8T_tLnZO3oQyGAWzVXxAQHTNo3Af6pFWqB8ICAvocx9O_WMOVhznB1FZEdsVULvpWidm8UNfOr9Efsw2FWczIDPUunEilRgWyB_4bhcVNgw05g7I-orFhF78rps5VlsQIJlomGgrJSGeUIqGw'
    vk_api_instance = get_vk_api(token)

    fields = 'sex,bdate,city,photo_100'
    if show_interests:
        fields += ',interests'

    user_info = vk_api_instance.users.get(user_ids=vk_user_id, fields=fields)[0]
    formatted_bdate = format_bdate(user_info.get('bdate', ''))

    interests_graph = create_interests_graph(user_info) if show_interests else None
    post_activity_graph = create_post_activity_graph(vk_api_instance, vk_user_id) if show_posts else None

    friends_gender_stats = friends_data = friends_gender_graph = None
    dating_recommendations = None
    if show_friends:
        friends_gender_stats, friends_data, friends_gender_graph = create_friends_stats(vk_api_instance, vk_user_id)
        dating_recommendations = generate_dating_recommendations(
            vk_api_instance,
            user_info,
            find_potential_connections(vk_api_instance, vk_user_id, user_info)
        )

    groups_info = top_groups_info = total_groups_graph = top_groups_graph = None
    if show_groups:
        groups_info, top_groups_info, total_groups_graph, top_groups_graph = create_groups_stats(vk_api_instance, vk_user_id)

    toxic_posts = find_toxic_posts(vk_api_instance, vk_user_id) if show_toxicity else None

    social_graph_img = generate_social_graph_image_with_avatars(vk_api_instance, vk_user_id)

    user_analytics = None
    if show_friends or show_groups:
        user_analytics = generate_user_analytics(
            user_info,
            friends_data if show_friends else None,
            groups_info if show_groups else None,
            top_groups_info if show_groups else None
        )

    return dict(
        user_info=user_info,
        formatted_bdate=formatted_bdate,
        interests_graph=interests_graph,
        post_activity_graph=post_activity_graph,
        friends_gender_stats=friends_gender_stats,
        friends_gender_graph=friends_gender_graph,
        friends_data=friends_data,
        groups_info=groups_info,
        top_groups_info=top_groups_info,
        total_groups_graph=total_groups_graph,
        top_groups_graph=top_groups_graph,
        social_graph_img=social_graph_img,
        dating_recommendations=dating_recommendations,
        user_analytics=user_analytics,
        toxic_posts=toxic_posts
    )


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        show_toxicity = 'show_toxicity' in request.form
        vk_url = request.form['vk_url']
        vk_user_id = extract_user_id(vk_url)

        if not vk_user_id:
            flash('Неверный URL профиля VK', 'danger')
            return redirect(url_for('profile'))

        show_interests = 'show_interests' in request.form
        show_posts = 'show_posts' in request.form
        show_friends = 'show_friends' in request.form
        show_groups = 'show_groups' in request.form
        show_toxicity = 'show_toxicity' in request.form  
        generate_graph = True

        try:
            token = 'vk1.a.USGB6XBqseXr9H8xXVtGRoQnwcM7veA31BKJFw1r-hH7SO1PbvGUrk4cCP3I5nOvVvKld8T_tLnZO3oQyGAWzVXxAQHTNo3Af6pFWqB8ICAvocx9O_WMOVhznB1FZEdsVULvpWidm8UNfOr9Efsw2FWczIDPUunEilRgWyB_4bhcVNgw05g7I-orFhF78rps5VlsQIJlomGgrJSGeUIqGw'
            vk_api_instance = get_vk_api(token)


            fields = 'sex,bdate,city,photo_100'
            if show_interests:
                fields += ',interests'

            user_info = vk_api_instance.users.get(user_ids=vk_user_id, fields=fields)[0]
            formatted_bdate = format_bdate(user_info.get('bdate', ''))


            interests_graph = None
            post_activity_graph = None
            friends_data = None
            friends_gender_stats = None
            friends_gender_graph = None
            groups_info = None
            top_groups_info = None
            total_groups_graph = None
            top_groups_graph = None
            social_graph_img = None
            dating_recommendations = None
            user_analytics = None
            toxic_posts = None  


            if show_interests:
                interests_graph = create_interests_graph(user_info)

            if show_posts:
                post_activity_graph = create_post_activity_graph(vk_api_instance, vk_user_id)

            if show_friends:
                friends_gender_stats, friends_data, friends_gender_graph = create_friends_stats(vk_api_instance,
                                                                                                vk_user_id)
                dating_recommendations = generate_dating_recommendations(
                    vk_api_instance,
                    user_info,
                    find_potential_connections(vk_api_instance, vk_user_id, user_info)
                )

            if show_groups:
                groups_info, top_groups_info, total_groups_graph, top_groups_graph = create_groups_stats(vk_api_instance, vk_user_id)

            if show_toxicity:  
                toxic_posts = find_toxic_posts(vk_api_instance, vk_user_id)

            if generate_graph:
                social_graph_img = generate_social_graph_image_with_avatars(vk_api_instance, vk_user_id)


            if show_friends or show_groups:
                user_analytics = generate_user_analytics(
                    user_info,
                    friends_data if show_friends else None,
                    groups_info if show_groups else None,
                    top_groups_info if show_groups else None
                )

            return render_template('profile.html',
                                   user_info=user_info,
                                   formatted_bdate=formatted_bdate,
                                   show_interests=show_interests,
                                   show_posts=show_posts,
                                   show_friends=show_friends,
                                   show_groups=show_groups,
                                   interests_graph=interests_graph,
                                   post_activity_graph=post_activity_graph,
                                   friends_gender_stats=friends_gender_stats,
                                   friends_gender_graph=friends_gender_graph,
                                   groups_info=groups_info,
                                   top_groups_info=top_groups_info,
                                   total_groups_graph=total_groups_graph,
                                   top_groups_graph=top_groups_graph,
                                   social_graph_img=social_graph_img,
                                   dating_recommendations=dating_recommendations,
                                   user_analytics=user_analytics,
                                   toxic_posts=toxic_posts,
                                   show_toxicity=show_toxicity       
                                   )

        except vk_api.exceptions.ApiError as e:
            flash(f'Ошибка VK API: {e}', 'danger')
        except RequestException as e:
            flash('Ошибка соединения с VK', 'danger')
        except Exception as e:
            flash('Неизвестная ошибка', 'danger')
            print(f"Ошибка: {e}\n{traceback.format_exc()}")

        return redirect(url_for('profile'))

    return render_template('profile.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


@app.route('/social_graph')
def social_graph():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('social_graph.html')



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
