import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import bcrypt

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change to a random string for security

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database connection function
def get_db_connection():
    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\Users\Sean Herrera\Desktop\Info Management Project\CollegeStudents.accdb;'
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

# ----------------- ROUTES -----------------

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

@app.route('/admindashboard')
@login_required
def admindashboard():
    if current_user.role != 'admin':
        flash("Access denied")
        return redirect(url_for('main'))
    return render_template('admindashboard.html')

# ----------------- CURRICULUM ROUTE -----------------
@app.route('/curriculum')
@login_required
def curriculum():
    conn = get_db_connection()
    cursor = conn.cursor()

    curriculum_data = []

    try:
        # Step 1: Get the logged-in student's Program, YearLevel, Semester
        cursor.execute("SELECT Program, YearLevel, Semester FROM BSCSStudents WHERE Email = ?", (current_user.email,))
        student = cursor.fetchone()
        print("DEBUG: Student lookup:", student)

        if student:
            program, year, semester = student
            table_map = {
                (1, 1): "BSCS_1_1",
                (1, 2): "BSCS_1_2",
                (2, 1): "BSCS_2_1",
                (2, 2): "BSCS_2_2",
                (3, 1): "BSCS_3_1",
                (3, 2): "BSCS_3_2",
                (4, 1): "BSCS_4_1",
                (4, 2): "BSCS_4_2"
            }
            table_name = table_map.get((year, semester))
            print("DEBUG: Selected table =", table_name)

            if table_name:
                # Step 2: Query curriculum with new columns
                query = f"""
                    SELECT cr.CourseCode,
                           cr.CourseName,
                           cr.Credits,
                           y.YearName AS YearLevel,
                           s.SemesterName AS Semester,
                           cur.Grades,
                           cur.Remarks,
                           cur.Instructor
                    FROM (([{table_name}] AS cur
                    INNER JOIN Courses AS cr ON cur.CourseID = cr.CourseID)
                    INNER JOIN YearLevels AS y ON cur.YearID = y.YearID)
                    INNER JOIN Semesters AS s ON cur.SemesterID = s.SemesterID;
                """
                print("DEBUG: Executing query:\n", query)

                cursor.execute(query)
                rows = cursor.fetchall()
                print("DEBUG: Joined rows:", rows)

                if rows:
                    columns = [col[0] for col in cursor.description]
                    curriculum_data = [dict(zip(columns, row)) for row in rows]
                    print("DEBUG: Curriculum rows fetched:", len(curriculum_data))
                else:
                    print("DEBUG: No rows returned from join")

    except pyodbc.Error as e:
        print("Error executing query:", e)
        curriculum_data = []

    conn.close()
    return render_template('subpages/curriculum.html', curriculum=curriculum_data)

#------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        email = request.form['email']
        major = request.form['major']
        password = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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

@app.route('/viewcourses', methods=['GET', 'POST'])
@login_required
def viewcourses():
    conn = get_db_connection()
    cursor = conn.cursor()

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

@app.route('/grades')
@login_required
def grades():
    return render_template('subpages/grades.html')

if __name__ == '__main__':
    app.run(debug=True)
