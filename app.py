import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from datetime import datetime, date

# Flask setup
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = 'your_secret_key_here'

# Initialize Bcrypt
bcrypt = Bcrypt(app)

# Database connection function
def get_db_connection():
    conn_str = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        r'DBQ=C:\Users\Sean Herrera\Desktop\CollegePortal\CollegeStudentDBTest.accdb;'
    )
    return pyodbc.connect(conn_str)

def safe_value(val):
    """
    This function ensures that the input value is safely processed.
    It returns None if the input is empty, 'None', or whitespace.
    """
    if val is None:
        return None
    val = str(val).strip()
    if val == "" or val.lower() == "none":
        return None
    return val

def parse_int(val):
    """
    This function safely converts a value to an integer.
    If the value is None or cannot be converted, it returns None.
    """
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None

def calculate_age(birthday):
    """
    This function calculates the age of a student based on their birthday.
    If the birthday is None or invalid, it returns None.
    """
    if not birthday:
        return None
    today = date.today()
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))

# ----------------- FLASK-LOGIN SETUP -----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"

class User(UserMixin):
    def __init__(self, id, student_number, role, username):
        self.id = id
        self.student_number = student_number  # student_number is now used
        self.role = role
        self.username = username  # username as the unique identifier

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserID, StudentNumber, Role, Username FROM Users WHERE UserID = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row.UserID, row.StudentNumber, row.Role, row.Username)  # Loading student_number and username
    return None

# ----------------- ROUTES -----------------
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    student_number = request.form.get("student_number")  # using student_number for login
    password = request.form.get("password")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT UserID, StudentNumber, Password, Role, Username FROM Users WHERE StudentNumber = ?",
        (student_number,)
    )
    user = cursor.fetchone()
    conn.close()

    # Verify password using bcrypt
    if user and bcrypt.check_password_hash(user.Password, password):
        user_obj = User(user.UserID, user.StudentNumber, user.Role, user.Username)  # Create User object
        login_user(user_obj)

        role = user.Role.lower()
        if role == "admin":
            return redirect(url_for("admin_dashboard"))
        elif role == "student":
            return redirect(url_for("student_portal"))
        else:
            return redirect(url_for("home"))
    else:
        flash("Invalid credentials. Please try again.")
        return redirect(url_for("home"))

@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role.lower() != "admin":
        return redirect(url_for("student_portal"))
    return render_template("admindashboard.html")

@app.route("/main")
@login_required
def student_portal():
    if current_user.role.lower() != "student":
        return redirect(url_for("admin_dashboard"))
    return render_template("main.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

#------------------

@app.route("/studentinfo")
@login_required
def studentinfo():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = int(current_user.id)

        cursor.execute("SELECT * FROM Students WHERE [UserID] = ?", (user_id,))
        student = cursor.fetchone()

        print("STUDENTINFO user_id =", user_id)
        print("STUDENTINFO student =", student)

        if not student:
            return redirect(url_for("register"))

        # student is a tuple, so map it into the structure expected by studentinfo.html
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

        student_data = {
            "personal": {
                "StudentID": student[0],
                "UserID": student[1],
                "FirstName": student[2],
                "LastName": student[3],
                "Program": program_map.get(student[4], "N/A"),
                "YearLevel": student[5],
                "Semester": student[6],
                "Status": student[7],
                "StudentNumber": student[8],
                "Birthday": student[9],
                "Age": student[10],
                "Birthplace": student[11],
                "Sex": student[12],
                "CellphoneNumber": student[13],
                "Email": student[14],
                "CivilStatus": student[15],
                "Nationality": student[16],
                "Religion": student[17],
            },
            "address": {
                "HouseNumber": student[18],
                "Street": student[19],
                "Village": student[20],
                "Barangay": student[21],
                "City": student[22],
                "Province": student[23],
                "ZIPCode": student[24],
                "TelephoneMobileNumber": student[25],
            },
            "emergency": {
                "ContactPerson": student[26],
                "Relation": student[27],
                "ContactNumber": student[28],
                "Address": student[29],
            }
        }

        return render_template("studentinfo.html", student_data=student_data)

    except Exception as e:
        print("STUDENTINFO ERROR:", repr(e))
        flash(f"Error loading student information: {e}", "danger")
        return redirect(url_for("register"))

    finally:
        cursor.close()
        conn.close()

# ----------------- CREATE ACCOUNT -----------------
@app.route("/createaccount", methods=["GET", "POST"])
def create_account():
    # Ensure only admin can access this route
    if current_user.role.lower() != 'admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        student_number = request.form.get("student_number")
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Check if the passwords match
        if password != confirm_password:
            flash("Passwords do not match. Please try again.")
            return redirect(url_for("create_account"))
        
        # Check if the student number already exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE StudentNumber = ?", (student_number,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Student number already exists. Please choose another.")
            return redirect(url_for("create_account"))
        
        # Check if the username already exists
        cursor.execute("SELECT * FROM Users WHERE Username = ?", (username,))
        existing_username = cursor.fetchone()

        if existing_username:
            flash("Username already exists. Please choose another.")
            return redirect(url_for("create_account"))
        
        # Hash the password using bcrypt before storing it
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Insert the new user into the database (no auto-login)
        cursor.execute(
            "INSERT INTO Users (StudentNumber, Username, Password, Role) VALUES (?, ?, ?, ?)",
            (student_number, username, hashed_password, 'student')  # Assuming role 'student'
        )
        conn.commit()
        conn.close()

        flash("Account created successfully! The user can now log in.")
        return redirect(url_for("admin_dashboard"))  # Redirect to the admin dashboard or another page

    return render_template("createacc.html")

# ----------------- REGISTER -----------------
@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    def safe_value(val):
        if val is None:
            return None
        val = str(val).strip()
        if val == "" or val.lower() == "none":
            return None
        return val

    def parse_int(val):
        val = safe_value(val)
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def calculate_age(bday):
        if not bday:
            return None
        today = date.today()
        return today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = int(current_user.id)

        # ONE source of truth:
        # If a row already exists in Students for this user, they are already registered.
        cursor.execute("SELECT * FROM Students WHERE [UserID] = ?", (user_id,))
        existing_student = cursor.fetchone()

        print("REGISTER user_id =", user_id)
        print("REGISTER existing_student =", existing_student)

        if request.method == "GET":
            if existing_student:
                return redirect(url_for("studentinfo"))

            return render_template(
                "register.html",
                username=getattr(current_user, "username", ""),
                student_number=getattr(current_user, "student_number", ""),
                masked_password="********"
            )

        # POST: do not insert duplicates
        if existing_student:
            flash("Student profile already exists.", "warning")
            return redirect(url_for("studentinfo"))

        # Personal info
        FirstName = safe_value(request.form.get("FirstName"))
        LastName = safe_value(request.form.get("LastName"))
        Program = parse_int(request.form.get("Program"))
        YearLevel = parse_int(request.form.get("YearLevel"))
        Semester = parse_int(request.form.get("Semester"))
        Status = safe_value(request.form.get("Status"))
        StudentNumber = safe_value(request.form.get("StudentNumber")) or safe_value(
            getattr(current_user, "student_number", None)
        )

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

        SameAddress = request.form.get("SameAddress")
        if SameAddress:
            Address = ", ".join(filter(None, [
                HouseNumber, Street, Village, Barangay, City, Province, ZIPCode
            ]))
        else:
            Address = ", ".join(filter(None, [
                safe_value(request.form.get("EmergencyHouseNumber")),
                safe_value(request.form.get("EmergencyStreet")),
                safe_value(request.form.get("EmergencyVillage")),
                safe_value(request.form.get("EmergencyBarangay")),
                safe_value(request.form.get("EmergencyCity")),
                safe_value(request.form.get("EmergencyProvince")),
                safe_value(request.form.get("EmergencyZIPCode")),
                safe_value(request.form.get("EmergencyTelephoneMobileNumber")),
            ]))

        values_tuple = (
            user_id, FirstName, LastName, Program, YearLevel, Semester, Status,
            StudentNumber, Birthday, Age, Birthplace, Sex, CellphoneNumber,
            Email, CivilStatus, Nationality, Religion,
            HouseNumber, Street, Village, Barangay, City, Province, ZIPCode, TelephoneMobileNumber,
            ContactPerson, Relation, ContactNumber, Address
        )

        cursor.execute("""
            INSERT INTO Students (
                [UserID], [FirstName], [LastName], [Program], [YearLevel], [Semester], [Status],
                [StudentNumber], [Birthday], [Age], [Birthplace], [Sex], [CellphoneNumber],
                [Email], [CivilStatus], [Nationality], [Religion],
                [HouseNumber], [Street], [Village], [Barangay], [City], [Province], [ZIPCode], [TelephoneMobileNumber],
                [ContactPerson], [Relation], [ContactNumber], [Address]
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, values_tuple)

        conn.commit()
        return redirect(url_for("studentinfo"))

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass

        flash(f"Error during registration: {e}", "danger")
        return render_template(
            "register.html",
            username=getattr(current_user, "username", ""),
            student_number=getattr(current_user, "student_number", ""),
            masked_password="********"
        )

    finally:
        cursor.close()
        conn.close()

#-------------------------------------------------------

@app.route("/change_password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_new_password")

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("register"))   # or your edit page route

    if len(new_password) < 6:
        flash("New password must be at least 6 characters.", "danger")
        return redirect(url_for("register"))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT Password FROM Users WHERE UserID = ?", (current_user.id,))
        row = cursor.fetchone()

        if not row or not bcrypt.check_password_hash(row.Password, current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("register"))

        hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        cursor.execute("UPDATE Users SET Password = ? WHERE UserID = ?", 
                       (hashed_password, current_user.id))
        conn.commit()

    except Exception as e:
        flash(f"Error changing password: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("register"))

#------------------------------------------------
@app.route("/edit_studentinfo", methods=["GET", "POST"])
@login_required
def edit_studentinfo():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = int(current_user.id)

        # Fetch the existing student data from the database
        cursor.execute("SELECT * FROM Students WHERE [UserID] = ?", (user_id,))
        student = cursor.fetchone()

        if not student:
            flash("No student profile found. Please complete registration first.", "warning")
            return redirect(url_for("register"))

        if request.method == "POST":
            # Extract form data
            FirstName = safe_value(request.form.get("FirstName"))
            LastName = safe_value(request.form.get("LastName"))
            Program = parse_int(request.form.get("Program"))
            YearLevel = parse_int(request.form.get("YearLevel"))
            Semester = parse_int(request.form.get("Semester"))
            Status = safe_value(request.form.get("Status"))
            StudentNumber = safe_value(request.form.get("StudentNumber"))

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

            # Address data
            HouseNumber = safe_value(request.form.get("HouseNumber"))
            Street = safe_value(request.form.get("Street"))
            Village = safe_value(request.form.get("Village"))
            Barangay = safe_value(request.form.get("Barangay"))
            City = safe_value(request.form.get("City"))
            Province = safe_value(request.form.get("Province"))
            ZIPCode = safe_value(request.form.get("ZIPCode"))
            TelephoneMobileNumber = safe_value(request.form.get("TelephoneMobileNumber"))

            # Emergency contact data
            ContactPerson = safe_value(request.form.get("ContactPerson"))
            ContactNumber = safe_value(request.form.get("ContactNumber"))
            Relation = safe_value(request.form.get("Relation"))
            EmergencyAddress = safe_value(request.form.get("EmergencyAddress"))

            # Update the student's information in the database
            cursor.execute("""
                UPDATE Students
                SET
                    [FirstName] = ?,
                    [LastName] = ?,
                    [Program] = ?,
                    [YearLevel] = ?,
                    [Semester] = ?,
                    [Status] = ?,
                    [StudentNumber] = ?,
                    [Birthday] = ?,
                    [Age] = ?,
                    [Birthplace] = ?,
                    [Sex] = ?,
                    [CellphoneNumber] = ?,
                    [Email] = ?,
                    [CivilStatus] = ?,
                    [Nationality] = ?,
                    [Religion] = ?,
                    [HouseNumber] = ?,
                    [Street] = ?,
                    [Village] = ?,
                    [Barangay] = ?,
                    [City] = ?,
                    [Province] = ?,
                    [ZIPCode] = ?,
                    [TelephoneMobileNumber] = ?,
                    [ContactPerson] = ?,
                    [Relation] = ?,
                    [ContactNumber] = ?,
                    [Address] = ?
                WHERE [UserID] = ?
            """, (
                FirstName, LastName, Program, YearLevel, Semester, Status,
                StudentNumber, Birthday, Age, Birthplace, Sex, CellphoneNumber,
                Email, CivilStatus, Nationality, Religion,
                HouseNumber, Street, Village, Barangay, City, Province, ZIPCode, TelephoneMobileNumber,
                ContactPerson, Relation, ContactNumber, EmergencyAddress,
                user_id
            ))

            conn.commit()
            return redirect(url_for("studentinfo"))

        # If the request is GET, populate the form with current data
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

        student_data = {
            "personal": {
                "FirstName": student[2],
                "LastName": student[3],
                "Program": program_map.get(student[4], "N/A"),
                "YearLevel": student[5],
                "Semester": student[6],
                "Status": student[7],
                "StudentNumber": student[8],
                "Birthday": student[9].strftime('%Y-%m-%d') if student[9] else '',
                "Age": student[10],
                "Birthplace": student[11],
                "Sex": student[12],
                "CellphoneNumber": student[13],
                "Email": student[14],
                "CivilStatus": student[15],
                "Nationality": student[16],
                "Religion": student[17],
            },
            "address": {
                "HouseNumber": student[18],
                "Street": student[19],
                "Village": student[20],
                "Barangay": student[21],
                "City": student[22],
                "Province": student[23],
                "ZIPCode": student[24],
                "TelephoneMobileNumber": student[25],
            },
            "emergency": {
                "ContactPerson": student[26],
                "Relation": student[27],
                "ContactNumber": student[28],
                "Address": student[29],
            }
        }

        return render_template("edit_studentinfo.html", student_data=student_data)

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass

        flash(f"Error updating student information: {e}", "danger")
        print(f"EDIT_STUDENTINFO ERROR: {repr(e)}")
        return redirect(url_for("studentinfo"))

    finally:
        cursor.close()
        conn.close()
#--------------------------------------------------------

if __name__ == "__main__":
    app.run(port=5000)