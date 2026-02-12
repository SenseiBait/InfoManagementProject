from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pyodbc
import bcrypt

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change to a random string for security

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database connection function
def get_db_connection():
    conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\Users\Sean Herrera\Desktop\Info Management Project\CollegeStudents.accdb;'
    return pyodbc.connect(conn_str)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, email, role):
        self.id = id
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserID, Email, Role FROM Users WHERE UserID = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1], user[2])
    return None

# Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, Email, Password, Role FROM Users WHERE Email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
            login_user(User(user[0], user[1], user[3]))
            # Redirect based on role
            if user[3] == 'admin':
                return redirect(url_for('admindashboard'))
            else:
                return redirect(url_for('main'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/main')
@login_required
def main():
    return render_template('main.html')

# ----------------- ADMIN ROUTES -----------------
@app.route('/admindashboard')
@login_required
def admindashboard():
    if current_user.role != 'admin':
        flash("Access denied")
        return redirect(url_for('main'))
    return render_template('admindashboard.html')

#---------------------------------------------------

@app.route('/viewcourses', methods=['GET', 'POST'])
@login_required
def viewcourses():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Courses list
    courses = [
        "BEED (Generalists)",
        "BSED MAJOR SOCIAL STUDIES",
        "BSED MAJOR VALUES",
        "BSED MAJOR ENGLISH",
        "BSBA HR MANAGEMENT",
        "BSBA OP MAN",
        "BSCS",
        "ACT SPECIAL MMA"
    ]

    selected_course = ""
    selected_year = ""
    search_query = ""
    students = []

    if request.method == 'POST':
        selected_course = request.form.get('course', '')
        selected_year = request.form.get('year', '')
        search_query = request.form.get('search', '')

        # Only query if at least one filter is applied
        if selected_course or selected_year or search_query:
            query = "SELECT FirstName, LastName, Email, Major, YearLevel FROM BSCSStudents WHERE 1=1"
            params = []

            if selected_course:
                query += " AND Major = ?"
                params.append(selected_course)

            if selected_year:
                query += " AND YearLevel = ?"
                params.append(selected_year)

            if search_query:
                query += " AND (FirstName LIKE ? OR LastName LIKE ? OR Email LIKE ?)"
                search_term = f"%{search_query}%"
                params.extend([search_term, search_term, search_term])

            cursor.execute(query, params)
            students = cursor.fetchall()

    conn.close()
    return render_template('subpages/viewcourses.html',
                           courses=courses,
                           students=students,
                           selected_course=selected_course,
                           selected_year=selected_year,
                           search_query=search_query)

# ----------------- LOGOUT -----------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ----------------- REGISTER -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        email = request.form['email']
        major = request.form['major']
        password = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # By default, new users are 'student'
        role = 'student'

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Users (Email, Password, Role) VALUES (?, ?, ?)",
            (email, password, role)
        )
        conn.commit()

        conn.close()

        flash('Registration successful! You can now log in.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/studentinfo')
@login_required
def studentinfo():
    return render_template('subpages/studentinfo.html')

@app.route('/schoolhistory')
@login_required
def schoolhistory():
    return render_template('subpages/schoolhistory.html')

@app.route('/form137')
@login_required
def form137():
    return render_template('subpages/form137.html')

@app.route('/courses')
@login_required
def courses():
    return render_template('subpages/courses.html')

@app.route('/curriculum')
@login_required
def curriculum():
    return render_template('subpages/curriculum.html')

@app.route('/grades')
@login_required
def grades():
    return render_template('subpages/grades.html')


if __name__ == '__main__':
    app.run(debug=True)