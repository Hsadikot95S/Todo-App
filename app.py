from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_pymongo import PyMongo
from flask import redirect, url_for
from bcrypt import hashpw, checkpw, gensalt
import csv
import os
from apscheduler.schedulers.background import BackgroundScheduler
import datetime

# App initialization
app = Flask(__name__)
app.config['SESSION_TYPE'] = 'mongodb'
app.config['SESSION_PERMANENT'] = True

# Set the session cookie to be secure (HTTPS-only) in production
app.config['SESSION_COOKIE_SECURE'] = True

# Set the session cookie to be accessible only via HTTP(S), not JavaScript
app.config['SESSION_COOKIE_HTTPONLY'] = True

#app.config['SECRET_KEY'] = os.urandom(24)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key')

app.config["MONGO_URI"] = "mongodb+srv://admin:test@cluster0.2pkodqh.mongodb.net/Cluster0"
mongo = PyMongo(app)

# Scheduler initialization
scheduler = BackgroundScheduler()
scheduler.start()

def send_reminder(username, todo_item):
    # Fetch user from MongoDB
    user = mongo.db.users.find_one({'username': username})

    # If user found, loop through todos and flash a reminder for matching todo
    if user:
        todos = user['todos']
        for todo in todos:
            if todo['item'] == todo_item:
                flash(f"Reminder: {todo_item} (Due: {todo['due_date']} {todo['due_time']})", 'info')
                break

# The main route rendering the index page
@app.route('/')
def index():


    # Initialize empty list for todos
    todos = []

    # Fetch user from session and load todos
    if 'username' in session:
        user = mongo.db.users.find_one({'username': session['username']})
        if user:
            todos = user['todos']
            return render_template('index.html', todos=todos)

    return redirect(url_for('register'))
# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Validate form data
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))

        # Check if username already exists
        existing_user = mongo.db.users.find_one({'username': username})
        if existing_user:
            flash('Username already exists!', 'error')
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = hashpw(password.encode('utf-8'), gensalt())

        # Store user data in MongoDB
        mongo.db.users.insert_one({'username': username, 'password': hashed_password, 'todos': []})

        # Redirect to index page after successful registration
        session['username'] = username  # Set session after registration
        return redirect(url_for('index'))

    return render_template('register.html')


    return render_template('register.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    # If request method is POST, login user
    if request.method == 'POST':
        user = mongo.db.users.find_one({'username': request.form['username']})
        if user and checkpw(request.form['password'].encode('utf-8'), user['password']):
            session['username'] = request.form['username']
            return redirect(url_for('index'))
        flash('Invalid username or password!', 'error')
    return render_template('login.html')

# Route for user logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Route for adding todo
@app.route('/add', methods=['POST'])
def add():
    if 'username' in session:
        # Create todo_item dict from form data
        todo_item = {
            'item': request.form['item'],
            'completed': False,
            'priority': request.form['priority'],
            'tags': [tag.strip() for tag in request.form.get('tags', '').split(',')],
            'created_date': request.form['created_date'],
            'due_date': request.form['due_date'],
            'alarm': 'alarm' in request.form
        }

        # If alarm is set, add reminder job to scheduler
        if todo_item['alarm']:
            reminder_datetime = datetime.datetime.combine(
                datetime.datetime.strptime(todo_item['due_date'], '%Y-%m-%d').date(),
                datetime.datetime.now().time()
            )
            scheduler.add_job(lambda: send_reminder(session['username'], todo_item['item']), 'date', run_date=reminder_datetime)

        # Update MongoDB document
        mongo.db.users.update_one(
            {'username': session['username']},
            {'$push': {'todos': todo_item}}
        )
    return redirect(url_for('index'))

# Route for marking a todo as completed
@app.route('/complete/<string:todo_item>')
def complete(todo_item):
    print(session['username'])
    if 'username' in session:
        mongo.db.users.update_one(
            {'username': session['username'], 'todos.item': todo_item},
            {'$set': {'todos.$.completed': True}}
        )
    return redirect(url_for('index'))

# Route for deleting a todo
@app.route('/delete/<string:todo_item>')
def delete(todo_item):
    if 'username' in session:
        mongo.db.users.update_one(
            {'username': session['username']},
            {'$pull': {'todos': {'item': todo_item}}}
        )
    return redirect(url_for('index'))

# Route for editing a todo
@app.route('/edit/<string:todo_item>', methods=['GET', 'POST'])
def edit(todo_item):
    if 'username' in session:
        user = mongo.db.users.find_one({'username': session['username'], 'todos.item': todo_item})
        if user:
            if request.method == 'POST':
                # Update MongoDB document with form data
                mongo.db.users.update_one(
                    {'username': session['username'], 'todos.item': todo_item},
                    {
                        '$set': {
                            'todos.$.item': request.form['item'],
                            'todos.$.priority': request.form['priority'],
                            'todos.$.tags': [tag.strip() for tag in request.form.get('tags', '').split(',')],
                            'todos.$.created_date': request.form['created_date'],
                            'todos.$.due_date': request.form['due_date'],
                            'todos.$.alarm': 'alarm' in request.form
                        }
                    }
                )
                return redirect(url_for('index'))
            else:
                # If request method is GET, render edit page with todo
                todo = next(todo for todo in user['todos'] if todo['item'] == todo_item)
                return render_template('edit.html', todo=todo)
    return redirect(url_for('login'))

# Route for viewing completed todos
@app.route('/completed')
def completed():
    if 'username' in session:
        user = mongo.db.users.find_one({'username': session['username']})
        if user:
            completed_todos = [todo for todo in user['todos'] if todo['completed']]
        else:
            completed_todos = []
        return render_template('completed.html', completed_todos=completed_todos)
    return redirect(url_for('login'))

# Route for exporting completed todos to CSV
@app.route('/export_csv')
def export():
    if 'username' in session:
        user = mongo.db.users.find_one({'username': session['username']})
        if user:
            completed_todos = [todo for todo in user['todos'] if todo['completed']]
            filepath = os.path.join(app.root_path, f"{session['username']}_completed_tasks.csv")
            with open(filepath, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Task', 'Priority', 'Tags', 'Created Date', 'Due Date', 'Alarm'])
                for todo in completed_todos:
                    writer.writerow([todo['item'], todo['priority'], ', '.join(todo['tags']),
                                     todo['created_date'], todo['due_date'], todo['alarm']])
            return send_file(filepath, as_attachment=True, mimetype='text/csv', attachment_filename=os.path.basename(filepath))
    return redirect(url_for('login'))

# Main driver function
if __name__ == '__main__':
    app.run(debug=True)