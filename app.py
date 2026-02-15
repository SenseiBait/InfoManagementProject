import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import bcrypt
import datetime
from datetime import datetime

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
@app.route("/accountregistration", methods=["GET", "POST"])
def account_register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("account_register"))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Check if email already exists
            cursor.execute("SELECT UserID FROM Users WHERE Email = ?", (email,))
            existing = cursor.fetchone()
            if existing:
                flash("Email already registered.", "danger")
                return redirect(url_for("account_register"))

            # Hash password
            hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

            # ✅ Insert new user with default role "student"
            cursor.execute(
                "INSERT INTO Users (Email, Password, Role) VALUES (?, ?, ?)",
                (email, hashed_pw.decode("utf-8"), "student")
            )
            conn.commit()

            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            print("DEBUG: Error during account registration:", e)
            flash("Error creating account. Please try again.", "danger")
        finally:
            cursor.close()
            conn.close()

    # ✅ Open to guests
    return render_template("accreg.html")

#------------------------------------------------------------------------------------

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

#--------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            UserID = current_user.id  

            # Personal info
            FirstName = request.form.get("FirstName")
            LastName = request.form.get("LastName")

            Program_raw = request.form.get("Program")
            Program = int(Program_raw) if Program_raw and Program_raw.isdigit() else None

            YearLevel_raw = request.form.get("YearLevel")
            YearLevel = int(YearLevel_raw) if YearLevel_raw and YearLevel_raw.isdigit() else None

            Semester_raw = request.form.get("Semester")
            Semester = int(Semester_raw) if Semester_raw and Semester_raw.isdigit() else None

            Status = request.form.get("Status")
            StudentNumber = request.form.get("StudentNumber")

            Birthday_raw = request.form.get("Birthday")
            Birthday = None
            if Birthday_raw:
                try:
                    Birthday = datetime.strptime(Birthday_raw, "%Y-%m-%d").date()
                except ValueError:
                    Birthday = None

            Age_raw = request.form.get("Age")
            Age = int(Age_raw) if Age_raw and Age_raw.isdigit() else None

            Birthplace = request.form.get("Birthplace")
            Sex = request.form.get("Sex")
            CellphoneNumber = request.form.get("CellphoneNumber")
            Email = request.form.get("Email")
            CivilStatus = request.form.get("CivilStatus")
            Nationality = request.form.get("Nationality")
            Religion = request.form.get("Religion")

            # Address info
            HouseNumber = request.form.get("HouseNumber")
            Street = request.form.get("Street")
            Village = request.form.get("Village")
            Barangay = request.form.get("Barangay")
            City = request.form.get("City")
            Province = request.form.get("Province")
            ZIPCode = request.form.get("ZIPCode")
            TelephoneMobileNumber = request.form.get("TelephoneMobileNumber")

            # Emergency contact
            ContactPerson = request.form.get("ContactPerson")
            ContactNumber = request.form.get("ContactNumber")
            Relation = request.form.get("Relation")

            # Emergency address logic
            SameAddress = request.form.get("SameAddress")
            if SameAddress:
                Address = ", ".join(filter(None, [
                    HouseNumber, Street, Village, Barangay, City, Province, ZIPCode
                ]))
            else:
                Address = ", ".join(filter(None, [
                    request.form.get('EmergencyHouseNumber'),
                    request.form.get('EmergencyStreet'),
                    request.form.get('EmergencyVillage'),
                    request.form.get('EmergencyBarangay'),
                    request.form.get('EmergencyCity'),
                    request.form.get('EmergencyProvince'),
                    request.form.get('EmergencyZIPCode')
                ]))
                tel = request.form.get('EmergencyTelephoneMobileNumber')
                if tel:
                    Address += f" (Tel: {tel})"

            # Final tuple (29 values)
            values_tuple = (
                UserID, FirstName, LastName, Program, YearLevel, Semester, Status,
                StudentNumber, Birthday, Age, Birthplace, Sex, CellphoneNumber,
                Email, CivilStatus, Nationality, Religion,
                HouseNumber, Street, Village, Barangay, City, Province, ZIPCode, TelephoneMobileNumber,
                ContactPerson, Relation, ContactNumber, Address
            )
            print("DEBUG values length:", len(values_tuple))  # must print 29

            cursor.execute("""
                INSERT INTO Students (
                    UserID, FirstName, LastName, Program, YearLevel, Semester, Status,
                    StudentNumber, Birthday, Age, Birthplace, Sex, CellphoneNumber,
                    Email, CivilStatus, Nationality, Religion,
                    HouseNumber, Street, Village, Barangay, City, Province, ZIPCode, TelephoneMobileNumber,
                    ContactPerson, Relation, ContactNumber, Address
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, values_tuple)
            conn.commit()

            flash("Registration successful!", "success")
            return redirect(url_for("studentinfo"))

        except Exception as e:
            print("DEBUG: Error during student insert:", e)
            flash("Error during registration. Please try again.", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template(
        "register.html",
        username=current_user.email,
        masked_password="********"
    )

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
        try:
            cursor.execute("""
                UPDATE Students
                SET FirstName=?, LastName=?, Program=?, YearLevel=?, Semester=?, Status=?,
                    StudentNumber=?, Birthday=?, Age=?, Birthplace=?, Sex=?, CellphoneNumber=?, Email=?,
                    CivilStatus=?, Nationality=?, Religion=?, HouseNumber=?, Street=?, Village=?, Barangay=?, City=?,
                    Province=?, ZIPCode=?, TelephoneMobileNumber=?, ContactPerson=?, Relation=?, ContactNumber=?, Address=?
                WHERE UserID=?
            """, (
                request.form.get('FirstName', ''), request.form.get('LastName', ''), request.form.get('Program', ''),
                request.form.get('YearLevel', ''), request.form.get('Semester', ''), request.form.get('Status', 'Active'),
                request.form.get('StudentNumber', ''), request.form.get('Birthday', ''), request.form.get('Age', ''),
                request.form.get('Birthplace', ''), request.form.get('Sex', ''), request.form.get('CellphoneNumber', ''),
                request.form.get('Email', ''), request.form.get('CivilStatus', ''), request.form.get('Nationality', ''),
                request.form.get('Religion', ''), request.form.get('HouseNumber', ''), request.form.get('Street', ''),
                request.form.get('Village', ''), request.form.get('Barangay', ''), request.form.get('City', ''),
                request.form.get('Province', ''), request.form.get('ZIPCode', ''), request.form.get('TelephoneMobileNumber', ''),
                request.form.get('ContactPerson', ''), request.form.get('Relation', ''), request.form.get('ContactNumber', ''),
                request.form.get('Address', ''), current_user.id
            ))
            conn.commit()
            flash("Student information updated successfully!", "success")
        except pyodbc.Error as e:
            flash(f"Error updating data: {e}", "danger")

    student_data = {'personal': {}, 'address': {}, 'emergency': {}}

    try:
        cursor.execute("SELECT * FROM Students WHERE UserID = ?", (current_user.id,))
        row = cursor.fetchone()
        student_dict = row_to_dict(cursor, row)

        if student_dict:
            student_data['personal'] = {
                'FirstName': student_dict.get('FirstName', ''),
                'LastName': student_dict.get('LastName', ''),
                'Program': student_dict.get('Program', ''),
                'YearLevel': student_dict.get('YearLevel', ''),
                'Semester': student_dict.get('Semester', ''),
                'Status': student_dict.get('Status', ''),
                'StudentNumber': student_dict.get('StudentNumber', ''),
                'Birthday': student_dict.get('Birthday', ''),
                'Age': student_dict.get('Age', ''),
                'Birthplace': student_dict.get('Birthplace', ''),
                'Sex': student_dict.get('Sex', ''),
                'CellphoneNumber': student_dict.get('CellphoneNumber', ''),
                'Email': student_dict.get('Email', ''),
                'CivilStatus': student_dict.get('CivilStatus', ''),
                'Nationality': student_dict.get('Nationality', ''),
                'Religion': student_dict.get('Religion', '')
            }
            student_data['address'] = {
                'HouseNumber': student_dict.get('HouseNumber', ''),
                'Street': student_dict.get('Street', ''),
                'Village': student_dict.get('Village', ''),
                'Barangay': student_dict.get('Barangay', ''),
                'City': student_dict.get('City', ''),
                'Province': student_dict.get('Province', ''),
                'ZIPCode': student_dict.get('ZIPCode', ''),
                'TelephoneMobileNumber': student_dict.get('TelephoneMobileNumber', '')
            }
            student_data['emergency'] = {
                'ContactPerson': student_dict.get('ContactPerson', ''),
                'Relation': student_dict.get('Relation', ''),
                'ContactNumber': student_dict.get('ContactNumber', ''),
                'Address': student_dict.get('Address', '')
            }

    except pyodbc.Error as e:
        flash(f"Error fetching data: {e}", "danger")
    finally:
        conn.close()

    if not student_data['personal']:
        flash("No student record found. Please register your information.", "warning")
        return redirect(url_for('register'))

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