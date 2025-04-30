from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse, parse_qs
import json
import os
import datetime
import re
import uuid
import socket
import platform
import matplotlib.pyplot as plt
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Имитация базы данных
users_db = {
    'admin': {
        'password': generate_password_hash('admin123'),
        'gender': 'male',
        'age': 30,
        'registration_stage': 'complete',
        'account_data': {
            'registration_ip': '127.0.0.1',
            'user_agent': 'Initial admin account',
            'device_id': 'admin-device'
        }
    }
}

# Временное хранилище для незавершенных регистраций
temp_registrations = {}

# Хранилище для аналитических данных
analytics_db = {}

DATA_FILE = 'account_data.json'
ACCOUNT_DATA_FILE = 'detailed_account_data.json'


def save_account_data(data):
    """Сохраняет данные аккаунта в файл"""
    existing_data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            existing_data = json.load(f)

    existing_data.update(data)

    with open(DATA_FILE, 'w') as f:
        json.dump(existing_data, f, indent=4)


def save_detailed_account_data(username, data):
    """Сохраняет подробные данные аккаунта"""
    existing_data = {}
    if os.path.exists(ACCOUNT_DATA_FILE):
        with open(ACCOUNT_DATA_FILE, 'r') as f:
            existing_data = json.load(f)

    existing_data[username] = data
    with open(ACCOUNT_DATA_FILE, 'w') as f:
        json.dump(existing_data, f, indent=4)


def parse_account_data(url):
    """Парсит данные аккаунта из URL"""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    account_data = {
        'source_url': url,
        'domain': parsed.netloc,
        'path': parsed.path,
        'params': query_params,
        'timestamp': datetime.datetime.now().isoformat()
    }

    if parsed.netloc not in analytics_db:
        analytics_db[parsed.netloc] = 0
    analytics_db[parsed.netloc] += 1

    return account_data


def parse_user_agent(user_agent):
    """Парсит User-Agent строку"""
    result = {
        'browser': 'Unknown',
        'os': 'Unknown',
        'device': 'Unknown'
    }

    # Браузеры
    if 'Firefox' in user_agent:
        result['browser'] = 'Firefox'
    elif 'Chrome' in user_agent:
        result['browser'] = 'Chrome'
    elif 'Safari' in user_agent:
        result['browser'] = 'Safari'
    elif 'Edge' in user_agent:
        result['browser'] = 'Edge'
    elif 'Opera' in user_agent:
        result['browser'] = 'Opera'
    elif 'MSIE' in user_agent or 'Trident' in user_agent:
        result['browser'] = 'Internet Explorer'

    # Операционные системы
    if 'Windows' in user_agent:
        result['os'] = 'Windows'
    elif 'Macintosh' in user_agent:
        result['os'] = 'Mac OS'
    elif 'Linux' in user_agent:
        result['os'] = 'Linux'
    elif 'Android' in user_agent:
        result['os'] = 'Android'
    elif 'iPhone' in user_agent or 'iPad' in user_agent:
        result['os'] = 'iOS'

    # Устройства
    if 'Mobile' in user_agent:
        result['device'] = 'Mobile'
    elif 'Tablet' in user_agent:
        result['device'] = 'Tablet'

    return result


def collect_account_data(request, action):
    """Собирает полные данные об аккаунте"""
    user_agent_data = parse_user_agent(request.headers.get('User-Agent', ''))
    ip_address = request.remote_addr

    # Генерация уникального ID устройства
    try:
        device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, request.headers.get('User-Agent', '') + ip_address))
    except:
        device_id = str(uuid.uuid4())


    account_data = {
        'action': action,
        'timestamp': datetime.datetime.now().isoformat(),
        'ip_address': ip_address,
        'user_agent': request.headers.get('User-Agent', ''),
        'device_info': {
            'device_id': device_id,
            'browser': user_agent_data['browser'],
            'os': user_agent_data['os'],
            'device_type': user_agent_data['device']
        },
        'technical_data': {
            'hostname': socket.gethostname(),
            'platform': platform.platform(),
            'system': platform.system(),
            'processor': platform.processor()
        }
    }

    # Добавляем данные из URL, если есть реферер
    if request.referrer:
        account_data.update(parse_account_data(request.referrer))

    return account_data


@app.route('/')
def index():
    if 'username' in session:
        user_data = users_db.get(session['username'], {})
        return render_template('index.html',
                               username=session['username'],
                               profile_data=user_data)
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Логин и пароль обязательны для заполнения!', 'error')
            return redirect(url_for('register'))

        if username in users_db or username in temp_registrations:
            flash('Пользователь уже существует!', 'error')
            return redirect(url_for('register'))

        # Сохраняем временные данные регистрации
        temp_registrations[username] = {
            'password': generate_password_hash(password),
            'registration_stage': 'credentials',
            'account_data': collect_account_data(request, 'registration_step1')
        }

        # Сохраняем технические данные
        save_detailed_account_data(username, temp_registrations[username]['account_data'])

        # Переходим ко второму этапу регистрации
        session['reg_username'] = username
        return redirect(url_for('register_profile'))

    return render_template('register_1.html')


@app.route('/register/profile', methods=['GET', 'POST'])
def register_profile():
    if 'reg_username' not in session or session['reg_username'] not in temp_registrations:
        flash('Пожалуйста, начните регистрацию с первого этапа', 'error')
        return redirect(url_for('register'))

    username = session['reg_username']

    if request.method == 'POST':
        gender = request.form.get('gender', '').strip()
        age = request.form.get('age', '').strip()

        try:
            age = int(age) if age else None
            if age and (age < 1 or age > 120):
                flash('Возраст должен быть от 1 до 120 лет', 'error')
                return redirect(url_for('register_profile'))
        except ValueError:
            flash('Введите корректный возраст', 'error')
            return redirect(url_for('register_profile'))

        # Получаем временные данные
        temp_data = temp_registrations[username]

        # Обновляем данные аккаунта
        account_data = temp_data['account_data']
        account_data.update(collect_account_data(request, 'registration_step2'))
        account_data.update({
            'gender': gender,
            'age': age,
            'action': 'registration_complete'
        })

        # Создаем запись пользователя
        users_db[username] = {
            'password': temp_data['password'],
            'gender': gender if gender else None,
            'age': age,
            'registration_stage': 'complete',
            'account_data': {
                'registration_ip': account_data['ip_address'],
                'user_agent': account_data['user_agent'],
                'device_id': account_data['device_info']['device_id']
            }
        }


        # Сохраняем данные
        save_account_data({username: account_data})
        save_detailed_account_data(username, account_data)

        # Очищаем временные данные
        del temp_registrations[username]
        session.pop('reg_username', None)

        flash('Регистрация завершена! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register_2.html', username=username)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = users_db.get(username)
        if user and check_password_hash(user['password'], password):
            session['username'] = username

            # Сохраняем данные входа
            account_data = collect_account_data(request, 'login')
            save_account_data({username: account_data})
            save_detailed_account_data(username, account_data)

            next_page = request.args.get('next', '')
            if next_page and urlparse(next_page).netloc == '':
                return redirect(next_page)
            return redirect(url_for('index'))

        flash('Неверный логин или пароль!', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login', next=request.path))

    username = session['username']
    user_data = users_db.get(username, {})

    # Собираем данные просмотра профиля
    account_data = collect_account_data(request, 'profile_view')
    account_data['viewed_section'] = request.args.get('show', 'main')
    save_account_data({username: account_data})
    save_detailed_account_data(username, account_data)

    profile_data = {
        'username': username,
        'gender': user_data.get('gender', 'не указан'),
        'age': user_data.get('age', 'не указан'),
        'account_data': {
            'registration_ip': user_data.get('account_data', {}).get('registration_ip', 'неизвестно'),
            'device_id': user_data.get('account_data', {}).get('device_id', 'неизвестно'),
            'last_login': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    }

    return render_template('profile.html', **profile_data)


@app.route('/analytics')
def analytics():
    if 'username' not in session or session['username'] != 'admin':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('index'))

    account_data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            account_data = json.load(f)

    detailed_data = {}
    if os.path.exists(ACCOUNT_DATA_FILE):
        with open(ACCOUNT_DATA_FILE, 'r') as f:
            detailed_data = json.load(f)

    return render_template('analytics.html',
                           analytics=analytics_db,
                           account_data=account_data,
                           detailed_data=detailed_data)

@app.route('/profile_setup', methods=['GET', 'POST'])
def profile_setup():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        gender = request.form.get('gender')
        age = request.form.get('age')
        interests = request.form.getlist('interests')

        if not gender or not age:
            flash('Пожалуйста, укажите пол и возраст!', 'error')
            return redirect(url_for('profile_setup'))

        username = session['username']
        users_db[username]['gender'] = gender
        users_db[username]['age'] = int(age)
        users_db[username]['interests'] = interests
        
        # Сохраняем данные для аналитики
        save_account_data({
            username: {
                'gender': gender,
                'age': age,
                'interests': interests,
                'timestamp': datetime.datetime.now().isoformat()
            }
        })
        
        flash('Данные успешно сохранены!', 'success')
        return redirect(url_for('profile'))
    
def generate_user_stats():
    # Собираем данные о пользователях
    genders = {}
    age_groups = {
        '18-25': 0,
        '26-35': 0,
        '36-45': 0,
        '46+': 0
    }
    
    for user, data in users_db.items():
        if isinstance(data, dict) and 'gender' in data:
            gender = data['gender']
            genders[gender] = genders.get(gender, 0) + 1
            
            if 'age' in data:
                age = data['age']
                if 18 <= age <= 25:
                    age_groups['18-25'] += 1
                elif 26 <= age <= 35:
                    age_groups['26-35'] += 1
                elif 36 <= age <= 45:
                    age_groups['36-45'] += 1
                else:
                    age_groups['46+'] += 1
    
    # Генерируем графики
    plt.figure(figsize=(12, 5))
    
    # График по полу
    plt.subplot(1, 2, 1)
    plt.pie(genders.values(), labels=genders.keys(), autopct='%1.1f%%')
    plt.title('Распределение по полу')
    
    # График по возрасту
    plt.subplot(1, 2, 2)
    plt.bar(age_groups.keys(), age_groups.values())
    plt.title('Распределение по возрасту')
    plt.xlabel('Возрастные группы')
    plt.ylabel('Количество пользователей')
    
    # Сохраняем в base64
    img = BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf-8')

@app.route('/user_stats')
def user_stats():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    stats_image = generate_user_stats()
    return render_template('user_stats.html', stats_image=stats_image)

@app.route('/logout')
def logout():
    if 'username' in session:
        username = session['username']
        account_data = collect_account_data(request, 'logout')
        save_account_data({username: account_data})
        save_detailed_account_data(username, account_data)

    session.pop('username', None)
    flash('Вы успешно вышли из системы.', 'info')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
