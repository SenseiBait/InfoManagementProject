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
    def safe_value(val):
        if val is None or val.strip() == '' or val.strip().lower() == 'none':
            return None
        return str(val).strip()

    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            UserID = int(current_user.id)

            # Personal info
            FirstName = safe_value(request.form.get("FirstName"))
            LastName = safe_value(request.form.get("LastName"))
            Program_raw = request.form.get("Program")
            Program = int(Program_raw) if Program_raw and Program_raw.isdigit() else None
            YearLevel_raw = request.form.get("YearLevel")
            YearLevel = int(YearLevel_raw) if YearLevel_raw and YearLevel_raw.isdigit() else None
            Semester_raw = request.form.get("Semester")
            Semester = int(Semester_raw) if Semester_raw and Semester_raw.isdigit() else None
            Status = safe_value(request.form.get("Status"))
            StudentNumber = safe_value(request.form.get("StudentNumber"))

            Birthday_raw = request.form.get("Birthday")
            Birthday = None
            if Birthday_raw:
                try:
                    Birthday = datetime.strptime(Birthday_raw, "%Y-%m-%d").date()
                except ValueError:
                    Birthday = None

            Age_raw = request.form.get("Age")
            Age = int(Age_raw) if Age_raw and Age_raw.isdigit() else None
            Birthplace = safe_value(request.form.get("Birthplace"))
            Sex = safe_value(request.form.get("Sex"))
            CellphoneNumber = safe_value(request.form.get("CellphoneNumber"))
            Email = safe_value(request.form.get("Email"))
            CivilStatus = safe_value(request.form.get("CivilStatus"))
            Nationality = safe_value(request.form.get("Nationality"))
            Religion = safe_value(request.form.get("Religion"))

            # Address info
            HouseNumber = safe_value(request.form.get("HouseNumber"))
            Street = safe_value(request.form.get("Street"))
            Village = safe_value(request.form.get("Village"))
            Barangay = safe_value(request.form.get("Barangay"))
            City = safe_value(request.form.get("City"))
            Province = safe_value(request.form.get("Province"))
            ZIPCode = safe_value(request.form.get("ZIPCode"))
            TelephoneMobileNumber = safe_value(request.form.get("TelephoneMobileNumber"))

            # Emergency contact
            ContactPerson = safe_value(request.form.get("ContactPerson"))
            ContactNumber = safe_value(request.form.get("ContactNumber"))
            Relation = safe_value(request.form.get("Relation"))

            # Emergency address logic
            SameAddress = request.form.get("SameAddress")
            if SameAddress:
                Address = ", ".join(filter(None, [
                    HouseNumber, Street, Village, Barangay, City, Province, ZIPCode
                ]))
            else:
                Address = ", ".join(filter(None, [
                    safe_value(request.form.get('EmergencyHouseNumber')),
                    safe_value(request.form.get('EmergencyStreet')),
                    safe_value(request.form.get('EmergencyVillage')),   # ✅ Village included
                    safe_value(request.form.get('EmergencyBarangay')),
                    safe_value(request.form.get('EmergencyCity')),
                    safe_value(request.form.get('EmergencyProvince')),
                    safe_value(request.form.get('EmergencyZIPCode'))
                ]))
                tel = safe_value(request.form.get('EmergencyTelephoneMobileNumber'))
                if tel:
                    Address += f" (Tel: {tel})"

            print("DEBUG Address before insert:", Address)

            values_tuple = (
                UserID, FirstName, LastName, Program, YearLevel, Semester, Status,
                StudentNumber, Birthday, Age, Birthplace, Sex, CellphoneNumber,
                Email, CivilStatus, Nationality, Religion,
                HouseNumber, Street, Village, Barangay, City, Province, ZIPCode, TelephoneMobileNumber,
                ContactPerson, Relation, ContactNumber, Address
            )

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
@app.route('/edit_studentinfo', methods=['GET', 'POST'])
@login_required
def edit_studentinfo():
    def safe_value(val):
        if val is None or str(val).strip() == '' or str(val).strip().lower() == 'none':
            return None
        return str(val).strip()

    def safe_int(val):
        if val and str(val).isdigit():
            return int(val)
        return None

    def safe_date(val):
        if val:
            try:
                return datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def row_to_dict(cursor, row):
        if row is None:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()

        # Personal info
        FirstName = safe_value(request.form.get('FirstName'))
        LastName = safe_value(request.form.get('LastName'))
        Program = safe_int(request.form.get('Program'))
        YearLevel = safe_int(request.form.get('YearLevel'))
        Semester = safe_int(request.form.get('Semester'))
        Birthday = safe_date(request.form.get('Birthday'))
        Age = safe_int(request.form.get('Age'))
        Status = safe_value(request.form.get('Status'))
        StudentNumber = safe_value(request.form.get('StudentNumber'))
        Birthplace = safe_value(request.form.get('Birthplace'))
        Sex = safe_value(request.form.get('Sex'))
        CellphoneNumber = safe_value(request.form.get('CellphoneNumber'))
        Email = safe_value(request.form.get('Email'))
        CivilStatus = safe_value(request.form.get('CivilStatus'))
        Nationality = safe_value(request.form.get('Nationality'))
        Religion = safe_value(request.form.get('Religion'))

        # Address info
        HouseNumber = safe_value(request.form.get('HouseNumber'))
        Street = safe_value(request.form.get('Street'))
        Village = safe_value(request.form.get('Village'))
        Barangay = safe_value(request.form.get('Barangay'))
        City = safe_value(request.form.get('City'))
        Province = safe_value(request.form.get('Province'))
        ZIPCode = safe_value(request.form.get('ZIPCode'))
        TelephoneMobileNumber = safe_value(request.form.get('TelephoneMobileNumber'))

        # Emergency contact
        ContactPerson = safe_value(request.form.get('ContactPerson'))
        ContactNumber = safe_value(request.form.get('ContactNumber'))
        Relation = safe_value(request.form.get('Relation'))
        Address = safe_value(request.form.get('EmergencyAddress'))  # stored in Address column

        try:
            cursor.execute("""
                UPDATE Students
                SET FirstName = ?, LastName = ?, Program = ?, YearLevel = ?, Semester = ?, 
                    Birthday = ?, Age = ?, Status = ?, StudentNumber = ?, Birthplace = ?, 
                    Sex = ?, CellphoneNumber = ?, Email = ?, CivilStatus = ?, Nationality = ?, Religion = ?,
                    HouseNumber = ?, Street = ?, Village = ?, Barangay = ?, City = ?, Province = ?, 
                    ZIPCode = ?, TelephoneMobileNumber = ?, ContactPerson = ?, ContactNumber = ?, Relation = ?, Address = ?
                WHERE UserID = ?
            """, (FirstName, LastName, Program, YearLevel, Semester, Birthday, Age, Status,
                  StudentNumber, Birthplace, Sex, CellphoneNumber, Email, CivilStatus, Nationality, Religion,
                  HouseNumber, Street, Village, Barangay, City, Province, ZIPCode, TelephoneMobileNumber,
                  ContactPerson, ContactNumber, Relation, Address, int(current_user.id)))  # force int

            if cursor.rowcount == 0:
                flash("No rows updated — check that UserID exists.", "warning")
            else:
                conn.commit()
                flash("Information updated successfully!", "success")
            return redirect(url_for('studentinfo'))
        except Exception as e:
            flash(f"Error updating information: {e}", "danger")
            print("SQL Error:", e)
        finally:
            cursor.close()
            conn.close()

    # GET request: load existing data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Students WHERE UserID = ?", (int(current_user.id),))
    row = cursor.fetchone()
    student_data = row_to_dict(cursor, row)
    cursor.close()
    conn.close()

    # Group into personal, address, emergency
    student_data['personal'] = {
        'FirstName': student_data.get('FirstName'),
        'LastName': student_data.get('LastName'),
        'Program': student_data.get('Program'),
        'YearLevel': student_data.get('YearLevel'),
        'Semester': student_data.get('Semester'),
        'Birthday': student_data.get('Birthday'),
        'Age': student_data.get('Age'),
        'Status': student_data.get('Status'),
        'StudentNumber': student_data.get('StudentNumber'),
        'Birthplace': student_data.get('Birthplace'),
        'Sex': student_data.get('Sex'),
        'CellphoneNumber': student_data.get('CellphoneNumber'),
        'Email': student_data.get('Email'),
        'CivilStatus': student_data.get('CivilStatus'),
        'Nationality': student_data.get('Nationality'),
        'Religion': student_data.get('Religion'),
    }

    student_data['address'] = {
        'HouseNumber': student_data.get('HouseNumber'),
        'Street': student_data.get('Street'),
        'Village': student_data.get('Village'),
        'Barangay': student_data.get('Barangay'),
        'City': student_data.get('City'),
        'Province': student_data.get('Province'),
        'ZIPCode': student_data.get('ZIPCode'),
        'TelephoneMobileNumber': student_data.get('TelephoneMobileNumber'),
    }

    student_data['emergency'] = {
        'ContactPerson': student_data.get('ContactPerson'),
        'ContactNumber': student_data.get('ContactNumber'),
        'Relation': student_data.get('Relation'),
        'Address': student_data.get('Address'),
    }

    return render_template('subpages/edit_studentinfo.html', student_data=student_data)

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

    def safe_value(val):
        return '' if val is None else val

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
                safe_value(request.form.get('FirstName')), safe_value(request.form.get('LastName')), request.form.get('Program'),
                request.form.get('YearLevel'), request.form.get('Semester'), safe_value(request.form.get('Status', 'Active')),
                safe_value(request.form.get('StudentNumber')), request.form.get('Birthday'), request.form.get('Age'),
                safe_value(request.form.get('Birthplace')), safe_value(request.form.get('Sex')), safe_value(request.form.get('CellphoneNumber')),
                safe_value(request.form.get('Email')), safe_value(request.form.get('CivilStatus')), safe_value(request.form.get('Nationality')),
                safe_value(request.form.get('Religion')), safe_value(request.form.get('HouseNumber')), safe_value(request.form.get('Street')),
                safe_value(request.form.get('Village')), safe_value(request.form.get('Barangay')), safe_value(request.form.get('City')),
                safe_value(request.form.get('Province')), safe_value(request.form.get('ZIPCode')), safe_value(request.form.get('TelephoneMobileNumber')),
                safe_value(request.form.get('ContactPerson')), safe_value(request.form.get('Relation')), safe_value(request.form.get('ContactNumber')),
                safe_value(request.form.get('Address')), current_user.id
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
                'FirstName': safe_value(student_dict.get('FirstName')),
                'LastName': safe_value(student_dict.get('LastName')),
                'Program': safe_value(student_dict.get('Program')),
                'YearLevel': safe_value(student_dict.get('YearLevel')),
                'Semester': safe_value(student_dict.get('Semester')),
                'Status': safe_value(student_dict.get('Status')),
                'StudentNumber': safe_value(student_dict.get('StudentNumber')),
                'Birthday': safe_value(student_dict.get('Birthday')),
                'Age': safe_value(student_dict.get('Age')),
                'Birthplace': safe_value(student_dict.get('Birthplace')),
                'Sex': safe_value(student_dict.get('Sex')),
                'CellphoneNumber': safe_value(student_dict.get('CellphoneNumber')),
                'Email': safe_value(student_dict.get('Email')),
                'CivilStatus': safe_value(student_dict.get('CivilStatus')),
                'Nationality': safe_value(student_dict.get('Nationality')),
                'Religion': safe_value(student_dict.get('Religion'))
            }
            student_data['address'] = {
                'HouseNumber': safe_value(student_dict.get('HouseNumber')),
                'Street': safe_value(student_dict.get('Street')),
                'Village': safe_value(student_dict.get('Village')),
                'Barangay': safe_value(student_dict.get('Barangay')),
                'City': safe_value(student_dict.get('City')),
                'Province': safe_value(student_dict.get('Province')),
                'ZIPCode': safe_value(student_dict.get('ZIPCode')),
                'TelephoneMobileNumber': safe_value(student_dict.get('TelephoneMobileNumber'))
            }
            student_data['emergency'] = {
                'ContactPerson': safe_value(student_dict.get('ContactPerson')),
                'Relation': safe_value(student_dict.get('Relation')),
                'ContactNumber': safe_value(student_dict.get('ContactNumber')),
                'Address': safe_value(student_dict.get('Address'))
            }

            print("DEBUG Address from DB:", student_dict.get('Address'))

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