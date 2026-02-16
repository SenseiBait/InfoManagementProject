import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import bcrypt
import datetime
from datetime import datetime
from datetime import datetime, date

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

#----------------- HELPER FUNCTIONS -----------------
def seed_student_curriculum(student_id, program_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Pull all courses for the program with YearLevel and Semester
        cursor.execute("""
            SELECT CourseID, CourseCode, CourseName, YearLevel, Semester
            FROM Courses
            WHERE ProgramID = ?
            ORDER BY YearLevel, Semester, CourseID
        """, (program_id,))
        courses = cursor.fetchall()

        print(f"DEBUG: Found {len(courses)} courses to seed for StudentID={student_id}")

        for course in courses:
            course_id = course[0]
            yearlevel = course[3]
            semester = course[4]

            cursor.execute("""
                INSERT INTO Student_Curriculum
                    (StudentID, CourseID, YearLevel, Semester, Status, Grade, Remarks, Instructor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                student_id,
                course_id,
                yearlevel,        # ✅ pulled from Courses table
                semester,         # ✅ pulled from Courses table
                "Not Taken",      # default status
                None,             # grade initially empty
                "",               # empty remarks
                ""                # empty instructor
            ))

        conn.commit()
        print(f"DEBUG: Curriculum seeded for StudentID={student_id} with full program courses")

    except Exception as e:
        print("DEBUG: Error during curriculum seeding:", e)
    finally:
        cursor.close()
        conn.close()

#-----------------User class for Flask-Login---------------------------
class User(UserMixin):
    def __init__(self, id, email, role):
        self.id = id
        self.email = email
        self.role = role

    @property
    def is_admin(self):
        return self.role == "admin"

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

#----------------------------------------------------

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

#----------------------------------------------------

@app.route('/main')
@login_required
def main():
    return render_template('main.html')

#----------------------------------------------------

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
        if val is None or str(val).strip() == '' or str(val).strip().lower() == 'none':
            return None
        return str(val).strip()

    def calculate_age(bday):
        """Return age in years given a date object."""
        if not bday:
            return None
        today = date.today()
        return today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))

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

            # Birthday + auto age
            Birthday_raw = request.form.get("Birthday")
            Birthday = None
            Age = None
            if Birthday_raw:
                try:
                    Birthday = datetime.strptime(Birthday_raw, "%Y-%m-%d").date()
                    Age = calculate_age(Birthday)
                except ValueError:
                    Birthday = None
                    Age = None

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
                    safe_value(request.form.get('EmergencyVillage')),
                    safe_value(request.form.get('EmergencyBarangay')),
                    safe_value(request.form.get('EmergencyCity')),
                    safe_value(request.form.get('EmergencyProvince')),
                    safe_value(request.form.get('EmergencyZIPCode'))
                ]))
                tel = safe_value(request.form.get('EmergencyTelephoneMobileNumber'))
                if tel:
                    Address += f" (Tel: {tel})"

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

            # ✅ Access-compatible way to get new StudentID
            cursor.execute("SELECT @@IDENTITY")
            student_id = cursor.fetchone()[0]

            print(f"DEBUG: Registered new student {student_id} - {FirstName} {LastName}")
            print(f"DEBUG: Program={Program}, YearLevel={YearLevel}, Semester={Semester}")

            # ✅ Seed their curriculum immediately
            seed_student_curriculum(student_id, Program, YearLevel, Semester)

            flash("Registration successful! Curriculum seeded.", "success")
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

    def calculate_age(bday):
        """Return age in years given a date object."""
        if not bday:
            return None
        today = date.today()
        return today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))

    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()

        # Personal info
        FirstName = safe_value(request.form.get('FirstName'))
        LastName = safe_value(request.form.get('LastName'))
        Program = safe_int(request.form.get('Program'))
        YearLevel = safe_int(request.form.get('YearLevel'))
        Semester = safe_int(request.form.get('Semester'))
        Birthday = safe_date(request.form.get('Birthday'))   # stored as date
        Age = calculate_age(Birthday)  # auto-calculate age
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
                  ContactPerson, ContactNumber, Relation, Address, int(current_user.id)))

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

    # --- FIX: normalize Birthday for <input type="date"> ---
    if student_data.get('Birthday'):
        try:
            if isinstance(student_data['Birthday'], (datetime, date)):
                student_data['Birthday'] = student_data['Birthday'].strftime("%Y-%m-%d")
            else:
                student_data['Birthday'] = datetime.strptime(str(student_data['Birthday']), "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            student_data['Birthday'] = None

    # Auto-calculate Age if Birthday exists
    age_val = None
    if student_data.get('Birthday'):
        try:
            bday_obj = datetime.strptime(student_data['Birthday'], "%Y-%m-%d").date()
            age_val = calculate_age(bday_obj)
        except Exception:
            age_val = None

    # Group into personal, address, emergency
    student_data['personal'] = {
        'FirstName': student_data.get('FirstName'),
        'LastName': student_data.get('LastName'),
        'Program': student_data.get('Program'),
        'YearLevel': student_data.get('YearLevel'),
        'Semester': student_data.get('Semester'),
        'Birthday': student_data.get('Birthday'),
        'Age': age_val if age_val is not None else student_data.get('Age'),
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

    # Human-readable program list
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

    # Map program names to numeric codes stored in DB
    program_map = {
        "BEED (Generalists)": "5",
        "BSED MAJOR SOCIAL STUDIES": "6",
        "BSED MAJOR VALUES": "7",
        "BSED MAJOR ENGLISH": "8",
        "BSBA HR MANAGEMENT": "4",
        "BSBA OP MAN": "3",
        "BSCS": "1",
        "ACT SPECIAL MMA": "2"
    }

    selected_course = ""
    selected_year = ""
    search_query = ""
    students = []

    if request.method == 'POST':
        selected_course = request.form.get('course', '').strip()
        selected_year = request.form.get('year', '').strip()
        search_query = request.form.get('search', '').strip()

        if selected_course or selected_year or search_query:
            query = """
                SELECT StudentID, FirstName, LastName, Email, Program, YearLevel
                FROM Students
                WHERE 1=1
            """
            params = []

            if selected_course:
                # If user typed a program name, convert to code
                if selected_course in program_map:
                    query += " AND Program = ?"
                    params.append(program_map[selected_course])
                else:
                    # Allow direct numeric input too
                    query += " AND Program = ?"
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
    return render_template(
        'subpages/viewcourses.html',
        courses=courses,
        students=students,
        selected_course=selected_course,
        selected_year=selected_year,
        search_query=search_query
    )

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
            # ✅ Program ID → Program Name mapping
            program_map = {
                1: "BSCS",
                2: "ACT",
                3: "BAOM",
                4: "BAHRM",
                5: "BEED",
                6: "BSED SOC",
                7: "BSED VAL",
                8: "BSED ENG"
            }

            student_data['personal'] = {
                'FirstName': safe_value(student_dict.get('FirstName')),
                'LastName': safe_value(student_dict.get('LastName')),
                'Program': program_map.get(student_dict.get('Program')),  # ✅ mapped name
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

#------------------------------------------------------------------------------------
@app.route('/update_curriculum/<int:student_id>', methods=['POST'])
@login_required
def update_curriculum(student_id):
    if not current_user.is_admin:
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all courses for this student
    cursor.execute("SELECT CourseID FROM Student_Curriculum WHERE StudentID = ?", (student_id,))
    courses = cursor.fetchall()

    for course in courses:
        course_id = course[0]

        # Pull values from the form
        yearlevel = request.form.get(f"yearlevel_{course_id}")
        semester = request.form.get(f"semester_{course_id}")
        status = request.form.get(f"status_{course_id}")
        grades = request.form.get(f"grades_{course_id}")
        remarks = request.form.get(f"remarks_{course_id}")
        instructor = request.form.get(f"instructor_{course_id}")

        # Update the row
        cursor.execute("""
            UPDATE Student_Curriculum
            SET YearLevel = ?, Semester = ?, Status = ?, Grades = ?, Remarks = ?, Instructor = ?
            WHERE StudentID = ? AND CourseID = ?
        """, (yearlevel, semester, status, grades, remarks, instructor, student_id, course_id))

    conn.commit()
    conn.close()

    # Redirect back to the admin curriculum detail page
    return redirect(url_for('admin_curriculum_detail', student_id=student_id))

#------------------------------------------------------------------------------------
@app.route('/admin_curriculum/<int:student_id>')
@login_required
def admin_curriculum(student_id):
    if not current_user.is_admin:
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    # Explicit aliases so pyodbc rows have predictable attribute names
    cursor.execute("""
        SELECT sc.CourseID AS CourseID,
               c.CourseCode AS CourseCode,
               c.CourseName AS CourseName,
               c.Credits AS Credits,
               sc.YearLevel AS YearLevel,
               sc.Semester AS Semester,
               sc.Status AS Status,
               sc.Grade AS Grade,
               sc.Remarks AS Remarks,
               sc.Instructor AS Instructor
        FROM Student_Curriculum sc
        INNER JOIN Courses c ON sc.CourseID = c.CourseID
        WHERE sc.StudentID = ?
        ORDER BY sc.YearLevel, sc.Semester, sc.CourseID
    """, (student_id,))
    rows = cursor.fetchall()

    print("DEBUG: curriculum rows fetched =", len(rows))
    for row in rows:
        print("DEBUG row:", row)

    # Group rows into dictionary by year/semester
    curriculum = {}
    for row in rows:
        year = row.YearLevel
        sem = row.Semester
        key = f"{year} Year - {sem} Semester"
        if key not in curriculum:
            curriculum[key] = []
        curriculum[key].append(row)

    cursor.execute("""
        SELECT StudentID, FirstName, LastName, Program, YearLevel, Semester
        FROM Students
        WHERE StudentID = ?
    """, (student_id,))
    student = cursor.fetchone()

    print("DEBUG: student record =", student)

    conn.close()

    return render_template(
        'subpages/admin_curriculum.html',
        student=student,
        curriculum=curriculum
    )
#------------------------------------------------------------------------------------
@app.route('/grades')
@login_required
def grades():
    return render_template('subpages/grades.html')

#------------------------------------------------------------------------------------
@app.route('/add_student', methods=['POST'])
@login_required
def add_student():
    if not current_user.is_admin:
        return "Unauthorized", 403

    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    program = request.form['program']
    year_level = request.form['year_level']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert the new student
    cursor.execute("""
        INSERT INTO Students (FirstName, LastName, Email, Program, YearLevel, UserID)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (first_name, last_name, email, program, year_level, current_user.id))
    conn.commit()

    # Get the new StudentID
    cursor.execute("SELECT SCOPE_IDENTITY()")
    student_id = cursor.fetchone()[0]
    conn.close()

    # ✅ Seed their curriculum immediately
    seed_student_curriculum(student_id, program)

    return redirect(url_for('viewcourses'))

#------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)