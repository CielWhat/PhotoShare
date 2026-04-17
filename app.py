from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from bcrypt import hashpw, gensalt, checkpw
from pathlib import Path

app = Flask(__name__)
app.secret_key = "your-secret-key-change-this-later"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    folder_path = db.Column(db.String(500), default="./test_photos")
    is_admin = db.Column(db.Boolean, default=False)

def is_image(filename):
    return filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'))

def is_video(filename):
    return filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and checkpw(password.encode('utf-8'), user.password_hash):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            session['root_path'] = user.folder_path
            return redirect(url_for('browse'))
        else:
            return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('browse'))
    return redirect(url_for('login'))

@app.route('/browse')
def browse():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'root_path' not in session:
        user = User.query.get(session['user_id'])
        if user:
            session['root_path'] = user.folder_path
        else:
            return redirect(url_for('logout'))

    current_path = request.args.get('path', '')
    root_path = Path(session['root_path']).resolve()

    if current_path:
        full_path = root_path / current_path.lstrip('/')
    else:
        full_path = root_path

    try:
        full_path.resolve().relative_to(root_path)
    except ValueError:
        return "Access denied", 403

    if not full_path.exists() or not full_path.is_dir():
        return "Path not found", 404

    items = []
    for item in sorted(full_path.iterdir()):
        item_path = str(item.relative_to(root_path))
        if not item_path.startswith('/'):
            item_path = '/' + item_path

        items.append({
            'name': item.name,
            'path': item_path,
            'is_dir': item.is_dir(),
            'is_image': item.is_file() and is_image(item.name),
            'is_video': item.is_file() and is_video(item.name)
        })

    parent_path = None
    if current_path and current_path != '/':
        parent = Path(current_path).parent
        if str(parent) != '.':
            parent_path = '/' + str(parent)
        else:
            parent_path = ''

    return render_template('browse.html',
                           items=items,
                           current_path=current_path,
                           parent_path=parent_path)

@app.route('/file/<path:filepath>')
def serve_file(filepath):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'root_path' not in session:
        user = User.query.get(session['user_id'])
        if user:
            session['root_path'] = user.folder_path
        else:
            return redirect(url_for('logout'))

    root_path = Path(session['root_path']).resolve()
    full_path = root_path / filepath.lstrip('/')

    try:
        full_path.resolve().relative_to(root_path)
    except ValueError:
        return "Access denied", 403

    if not full_path.exists() or not full_path.is_file():
        return "File not found", 404

    return send_from_directory(str(full_path.parent), full_path.name)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Create database and admin user
with app.app_context():
    db.create_all()

    # Create admin user if not exists
    if not User.query.filter_by(username="admin").first():
        admin_pw = hashpw("admin123".encode('utf-8'), gensalt())
        admin = User(username="admin", password_hash=admin_pw, folder_path="./test_photos", is_admin=True)
        db.session.add(admin)
        db.session.commit()
        print("=" * 50)
        print("Admin created: admin / admin123")
        print("=" * 50)
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    message = None

    if request.method == 'POST':
        # Delete user
        if 'delete_id' in request.form:
            user_id = request.form['delete_id']
            user = User.query.get(user_id)
            if user and user.id != session['user_id']:
                db.session.delete(user)
                db.session.commit()
                message = {'type': 'success', 'text': f'User {user.username} deleted'}
            else:
                message = {'type': 'error', 'text': 'Cannot delete this user'}

        # Create new user
        elif 'username' in request.form:
            username = request.form['username']
            password = request.form['password']
            folder_path = request.form['folder_path']
            is_admin = 'is_admin' in request.form

            if User.query.filter_by(username=username).first():
                message = {'type': 'error', 'text': 'Username already exists'}
            else:
                password_hash = hashpw(password.encode('utf-8'), gensalt())
                new_user = User(
                    username=username,
                    password_hash=password_hash,
                    folder_path=folder_path,
                    is_admin=is_admin
                )
                db.session.add(new_user)
                db.session.commit()
                message = {'type': 'success', 'text': f'User {username} created'}

    users = User.query.all()
    return render_template('admin.html', users=users, message=message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)