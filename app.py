import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import bcrypt
import datetime


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
@app.route('/courses')
@login_required
def courses():
    conn = get_db_connection()
    cursor = conn.cursor()
    courses_data = []

    try:
        # Step 1: Get the logged-in student's Program, YearLevel, Semester
        cursor.execute("SELECT Program, YearLevel, Semester FROM Students WHERE UserID = ?", (current_user.id,))
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
                    courses_data = [dict(zip(columns, row)) for row in rows]
                    print("DEBUG: Courses rows fetched:", len(courses_data))
                else:
                    print("DEBUG: No rows returned from join")

    except pyodbc.Error as e:
        print("Error executing query:", e)
        courses_data = []

    conn.close()
    return render_template('subpages/courses.html', courses=courses_data)


#------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

#----------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        first_name = request.form['FirstName']
        last_name = request.form['LastName']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 1. Insert into Users table
            cursor.execute("""
                INSERT INTO Users (Username, Password)
                VALUES (?, ?)
            """, (username, password))
            conn.commit()

            # 2. Get the new UserID
            cursor.execute("SELECT @@IDENTITY")
            new_user_id = cursor.fetchone()[0]

            # 3. Insert into Students table linked to UserID
            cursor.execute("""
                INSERT INTO Students (UserID, FirstName, LastName, Program, YearLevel, Semester, Status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                new_user_id, first_name, last_name,
                request.form.get('Program', ''), 
                request.form.get('YearLevel', ''), 
                request.form.get('Semester', ''), 
                request.form.get('Status', 'Active')
            ))
            conn.commit()

            flash("Registration successful! Student record created.", "success")
            return redirect(url_for('login'))

        except pyodbc.Error as e:
            flash(f"Error during registration: {e}", "danger")
        finally:
            conn.close()

    return render_template('register.html')


#------------------------------------------------------------------------------------

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

#------------------------------------------------------------------------------------
@app.route('/studentinfo', methods=['GET', 'POST'])
@login_required
def studentinfo():
    conn = get_db_connection()
    cursor = conn.cursor()

    def row_to_dict(cursor, row):
        if row is None:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    if request.method == 'POST':
        # Handle form submission: insert new student record linked to current user
        try:
            cursor.execute("""
                INSERT INTO Students (UserID, FirstName, LastName, Program, YearLevel, Semester, Status,
                                      StudentNumber, Birthday, Age, Birthplace, Sex, CellphoneNumber,
                                      Email, CivilStatus, Nationality, Religion,
                                      HouseNumber, Street, Barangay, City, Province, ZipCode,
                                      [Telphone/MobileNumber], ContactPerson, Relation, ContactNumber, Address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                current_user.id,  # <-- link student record to logged-in user
                request.form['FirstName'], request.form['LastName'], request.form['Program'],
                request.form['YearLevel'], request.form['Semester'], request.form['Status'],
                request.form['StudentNumber'], request.form['Birthday'], request.form['Age'],
                request.form['Birthplace'], request.form['Sex'], request.form['CellphoneNumber'],
                request.form['Email'], request.form['CivilStatus'], request.form['Nationality'],
                request.form['Religion'], request.form['HouseNumber'], request.form['Street'],
                request.form['Barangay'], request.form['City'], request.form['Province'],
                request.form['ZipCode'], request.form['Telphone/MobileNumber'],
                request.form['ContactPerson'], request.form['Relation'],
                request.form['ContactNumber'], request.form['Address']
            ))
            conn.commit()
            flash("Student information created successfully!", "success")
            return redirect(url_for('studentinfo'))
        except pyodbc.Error as e:
            flash(f"Error inserting data: {e}", "danger")

    student_data = {
        'personal': None,
        'address': None,
        'emergency': None
    }

    try:
        # Query student record by UserID
        query = """
            SELECT s.StudentID, s.FirstName, s.LastName, p.ProgramName, 
                   s.YearLevel, s.Semester, s.Status,
                   s.StudentNumber, s.Birthday, s.Age, s.Birthplace, s.Sex, s.CellphoneNumber,
                   s.Email, s.CivilStatus, s.Nationality, s.Religion,
                   s.HouseNumber, s.Street, s.Barangay, s.City, s.Province, s.ZipCode,
                   s.[Telphone/MobileNumber], s.ContactPerson, s.Relation, s.ContactNumber, s.Address
            FROM Students AS s
            LEFT JOIN Programs AS p ON s.Program = p.ProgramID
            WHERE s.UserID = ?
        """
        cursor.execute(query, (current_user.id,))
        row = cursor.fetchone()
        student_dict = row_to_dict(cursor, row)

        if student_dict:
            # Format birthday nicely
            birthday = student_dict['Birthday']
            if isinstance(birthday, (datetime.date, datetime.datetime)):
                birthday_str = birthday.strftime("%B %d, %Y")
            else:
                birthday_str = birthday if birthday else ""

            student_data['personal'] = {
                'FirstName': student_dict['FirstName'],
                'LastName': student_dict['LastName'],
                'Program': student_dict['ProgramName'] if student_dict['ProgramName'] else student_dict['Program'],
                'YearLevel': student_dict['YearLevel'],
                'Semester': student_dict['Semester'],
                'Status': student_dict['Status'],
                'StudentNumber': student_dict['StudentNumber'],
                'Birthday': birthday_str,
                'Age': student_dict['Age'],
                'Birthplace': student_dict['Birthplace'],
                'Sex': student_dict['Sex'],
                'CellphoneNumber': student_dict['CellphoneNumber'],
                'Email': student_dict['Email'],
                'CivilStatus': student_dict['CivilStatus'],
                'Nationality': student_dict['Nationality'],
                'Religion': student_dict['Religion']
            }
            student_data['address'] = {
                'HouseNumber': student_dict['HouseNumber'],
                'Street': student_dict['Street'],
                'Barangay': student_dict['Barangay'],
                'City': student_dict['City'],
                'Province': student_dict['Province'],
                'ZipCode': student_dict['ZipCode']
            }
            student_data['emergency'] = {
                'Telphone/MobileNumber': student_dict['Telphone/MobileNumber'],
                'ContactPerson': student_dict['ContactPerson'],
                'Relation': student_dict['Relation'],
                'ContactNumber': student_dict['ContactNumber'],
                'Address': student_dict['Address']
            }

    except pyodbc.Error as e:
        flash(f"Error fetching data: {e}", "danger")
    finally:
        conn.close()

    # If no student record exists, show register.html
    if not student_data['personal']:
        return render_template('register.html')

    return render_template('subpages/studentinfo.html', student_data=student_data)

#------------------------------------------------------------------------------------

@app.route('/schoolhistory')
@login_required
def schoolhistory():
    return render_template('subpages/schoolhistory.html')

@app.route('/form137')
@login_required
def form137():
    return render_template('subpages/form137.html')

#------------------------------------------------------------------------------------
@app.route('/curriculum')
@login_required
def curriculum():
    conn = get_db_connection()
    cursor = conn.cursor()
    curriculum_data = {}

    try:
        # Lookup student by UserID (not Email anymore)
        cursor.execute("SELECT Program FROM Students WHERE UserID = ?", (current_user.id,))
        student = cursor.fetchone()

        if student:
            program = student[0]

            program_tables = [
                ("1st Year - 1st Semester", "BSCS_1_1"),
                ("1st Year - 2nd Semester", "BSCS_1_2"),
                ("2nd Year - 1st Semester", "BSCS_2_1"),
                ("2nd Year - 2nd Semester", "BSCS_2_2"),
                ("3rd Year - 1st Semester", "BSCS_3_1"),
                ("3rd Year - 2nd Semester", "BSCS_3_2"),
                ("4th Year - 1st Semester", "BSCS_4_1"),
                ("4th Year - 2nd Semester", "BSCS_4_2")
            ]

            for year_sem, table_name in program_tables:
                query = f"""
                    SELECT cr.CourseCode,
                           cr.CourseName,
                           cr.Credits,
                           cur.Grades,
                           cur.Remarks,
                           cur.Instructor
                    FROM ([{table_name}] AS cur
                    INNER JOIN Courses AS cr ON cur.CourseID = cr.CourseID);
                """
                cursor.execute(query)
                rows = cursor.fetchall()

                if rows:
                    columns = [col[0] for col in cursor.description]
                    curriculum_data[year_sem] = [dict(zip(columns, row)) for row in rows]

    except pyodbc.Error as e:
        print("Error executing query:", e)
        curriculum_data = {}

    conn.close()
    return render_template('subpages/curriculum.html', curriculum=curriculum_data)


# ✅ Route for checkbox form submission
@app.route('/update_curriculum', methods=['POST'])
@login_required
def update_curriculum():
    if not current_user.is_admin:
        return "Unauthorized", 403

    selected_courses = request.form.getlist('selected_courses')
    print("DEBUG: Selected courses:", selected_courses)

    # Placeholder: add DB update logic here later
    return redirect(url_for('curriculum'))

#------------------------------------------------------------------------------------

@app.route('/grades')
@login_required
def grades():
    return render_template('subpages/grades.html')

if __name__ == '__main__':
    app.run(debug=True)
