from flask import Flask,request,redirect,session,render_template
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import jsonify

cache = {}


def get_db_connection():
   conn = sqlite3.connect("database.db")
   conn.row_factory = sqlite3.Row
   return conn

def init_db():
   conn = sqlite3.connect("database.db")
   cursor = conn.cursor()

   #users table schema
   cursor.execute("""
   CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      email TEXT unique,
      password TEXT,
      role TEXT,
      is_active INTEGER DEFAULT 1
   )
   """)

   #DOCTORS
   cursor.execute("""
   CREATE TABLE IF NOT EXISTS doctors(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      specialization TEXT,
      availability TEXT
   )
   """)

   #APPOINTMENTS
   cursor.execute("""
   CREATE TABLE IF NOT EXISTS appointments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      doctor_id INTEGER,
      patient_id INTEGER,
      date TEXT,
      time TEXT,
      status TEXT
   )
   """)

   #TREATMENTS
   cursor.execute("""
   CREATE TABLE IF NOT EXISTS treatments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      appointment_id INTEGER,
      diagnosis TEXT,
      prescription TEXT,
      notes TEXT
   )
   """)

   cursor.execute("""
      INSERT OR IGNORE INTO users(name , email , password, role)
      VALUES (?, ?, ?, ?)
      """, (
         "Admin",
         "admin@gmail.com",
         generate_password_hash("admin123"),
         "admin"
      ))

   conn.commit()
   conn.close()



app = Flask(__name__)
app.secret_key = "supersecret123"

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login",methods = ["GET","POST"])
def login():
   if request.method == "POST":
      email = request.form["email"]
      password = request.form["password"]

      conn = get_db_connection()
      user = conn.execute(
         "SELECT * FROM users WHERE email = ?",
         (email,)
      ).fetchone()
      conn.close()

      if not user or not check_password_hash(user["password"], password):
         return "Invalid Credentials"
      
      if user["is_active"]==0:
         return "Account Deactivated"
      
      session["user_id"] = user["id"]
      session["role"] = user["role"]

      if user["role"] == "admin":
         return redirect("/admin_dashboard")
      
      elif user["role"] == "doctor":
         return redirect("/doctor_dashboard")
      
      elif user["role"] == "patient":
         return redirect("/patient_vue")
   
   return render_template("login.html")



@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")



#patient registration
@app.route("/register",methods = ["GET","POST"])
def register():
   if request.method=="POST":
      name = request.form["name"]
      email = request.form["email"]
      password = generate_password_hash(request.form["password"])

      conn = get_db_connection()

      conn.execute("""
         INSERT INTO users(name,email,password,role)
         VALUES(?,?,?,?)
         """, (name , email,password,"patient"))
      
      conn.commit()
      conn.close()

      return "Registration Successful"
   
   return render_template("register.html")


@app.route("/add_doctor",methods=["GET","POST"])
def add_doctor():
   if "user_id" not in session or session.get("role")!="admin":
      return "Unauthorised access"
   
   if request.method=="POST":
      name = request.form["name"]
      email = request.form["email"]
      password = generate_password_hash(request.form["password"])
      specialization = request.form["specialization"]

      conn = get_db_connection()

      cursor = conn.execute("""
         INSERT INTO users (name , email , password, role)
         VALUES (?,?,?,?)
         """,(name , email ,password,"doctor"))
      
      user_id = cursor.lastrowid

      # creating doctor profile
      conn.execute("""
         INSERT INTO doctors(user_id,specialization,availability)
         VALUES(?,?,?)
         """,(user_id,specialization,""))
      
      conn.commit()
      conn.close()

      return "Doctor added Successfully"
   
   return render_template("add_doctor.html")




@app.route("/admin_dashboard")
def admin_dashboard():

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = get_db_connection()

    # counts
    if "admin_stats" in cache:
      total_doctors, total_patients, total_appointments = cache["admin_stats"]
    else:
      total_doctors = conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
      total_patients = conn.execute("SELECT COUNT(*) FROM users WHERE role='patient'").fetchone()[0]
      total_appointments = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]

    cache["admin_stats"] = (total_doctors, total_patients, total_appointments)


    # all appointments
    appointments = conn.execute("""
        SELECT appointments.*, u1.name as patient_name, u2.name as doctor_name
        FROM appointments
        JOIN users u1 ON appointments.patient_id = u1.id
        JOIN doctors d ON appointments.doctor_id = d.id
        JOIN users u2 ON d.user_id = u2.id
        ORDER BY date DESC, time DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_doctors=total_doctors,
        total_patients=total_patients,
        total_appointments=total_appointments,
        appointments=appointments
    )

@app.route("/view_doctors")
def view_doctors():

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = get_db_connection()

    search = request.args.get("search", "")

    doctors = conn.execute("""
      SELECT doctors.id, users.name, users.email, users.is_active, doctors.specialization
      FROM doctors
      JOIN users ON doctors.user_id = users.id
      WHERE users.name LIKE ? OR doctors.specialization LIKE ?
    """, (f"%{search}%", f"%{search}%")).fetchall()

    conn.close()

    return render_template("view_doctors.html", doctors=doctors)




@app.route("/toggle_doctor/<int:doc_id>")
def toggle_doctor(doc_id):

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = get_db_connection()

    doctor = conn.execute("""
        SELECT user_id FROM doctors WHERE id=?
    """, (doc_id,)).fetchone()

    if doctor:
        user_id = doctor["user_id"]

        current = conn.execute("""
            SELECT is_active FROM users WHERE id=?
        """, (user_id,)).fetchone()

        new_status = 0 if current["is_active"] == 1 else 1

        conn.execute("""
            UPDATE users SET is_active=? WHERE id=?
        """, (new_status, user_id))

        conn.commit()

    conn.close()

    return redirect("/view_doctors")



@app.route("/delete_doctor/<int:doc_id>")
def delete_doctor(doc_id):

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = get_db_connection()

    doctor = conn.execute("""
        SELECT user_id FROM doctors WHERE id=?
    """, (doc_id,)).fetchone()

    if doctor:
        user_id = doctor["user_id"]

        # delete related appointments
        conn.execute("DELETE FROM appointments WHERE doctor_id=?", (doc_id,))

        # delete doctor
        conn.execute("DELETE FROM doctors WHERE id=?", (doc_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))

        conn.commit()

    conn.close()

    return redirect("/view_doctors")





@app.route("/view_patients")
def view_patients():

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = get_db_connection()

    search = request.args.get("search", "")

    patients = conn.execute("""
      SELECT * FROM users 
      WHERE role='patient' AND (name LIKE ? OR email LIKE ?)
    """, (f"%{search}%", f"%{search}%")).fetchall()

    conn.close()

    return render_template("view_patients.html", patients=patients)



@app.route("/toggle_patient/<int:user_id>")
def toggle_patient(user_id):

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = get_db_connection()

    patient = conn.execute("""
        SELECT is_active FROM users WHERE id=? AND role='patient'
    """, (user_id,)).fetchone()

    if patient:
        new_status = 0 if patient["is_active"] == 1 else 1

        conn.execute("""
            UPDATE users SET is_active=? WHERE id=?
        """, (new_status, user_id))

        conn.commit()

    conn.close()

    return redirect("/view_patients")




@app.route("/doctor_dashboard")
def doctor_dashboard():
   
   if "user_id" not in session:
      return redirect("/login")
   
   conn = get_db_connection()

   # get doctor id from doctors table
   doctor = conn.execute("""
            SELECT id FROM DOCTORS WHERE user_id = ?
            """,(session["user_id"],)).fetchone()
   
   if doctor is None:
        conn.close()
        return "Doctor not found"
   
   doctor_id = doctor["id"]
   
   # get all appointments of this doctor
   appointments = conn.execute("""
            SELECT appointments.id, users.name, appointments.date,
            appointments.time, appointments.status FROM appointments
            JOIN users ON appointments.patient_id = users.id
            WHERE appointments.doctor_id = ?
             """,(doctor_id,)).fetchall()
   
   doctors = conn.execute("""
      SELECT doctors.id, users.name
      FROM doctors
      JOIN users ON doctors.user_id = users.id
   """).fetchall()

   conn.close()

   return render_template(
      "doctor_dashboard.html",
      appointments=appointments,
      doctors=doctors
   )



@app.route("/update_status/<int:app_id>", methods=["POST"])
def update_status(app_id):

   if "user_id" not in session or session.get("role") != "doctor":
      return redirect("/login")

   status = request.form.get("status")

   if status not in ["completed", "cancelled"]:
      return "Invalid status"

   conn = get_db_connection()

    # get doctor_id
   doctor = conn.execute("""
        SELECT id FROM doctors WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

   if doctor is None:
      conn.close()
      return "Doctor not found"

   doctor_id = doctor["id"]

    # check ownership
   appointment = conn.execute("""
      SELECT * FROM appointments 
      WHERE id = ? AND doctor_id = ?
    """, (app_id, doctor_id)).fetchone()

   if appointment is None:
        conn.close()
        return "Unauthorized action"

    # update
   conn.execute("""
        UPDATE appointments SET status = ? WHERE id = ?
    """, (status, app_id))

   conn.commit()
   conn.close()

   return redirect("/doctor_dashboard")



# @app.route("/patient_dashboard")
# def patient_dashboard():
#     if "user_id" not in session or session.get("role") != "patient":
#         return "Unauthorised access"

#     conn = get_db_connection()

#     doctors = conn.execute("""
#         SELECT doctors.id, users.name, doctors.specialization
#         FROM doctors
#         JOIN users ON doctors.user_id = users.id
#     """).fetchall()


#     appointments = conn.execute("""
#       SELECT appointments.*, users.name as doctor_name,
#             treatments.diagnosis, treatments.prescription
#       FROM appointments
#       JOIN doctors ON appointments.doctor_id = doctors.id
#       JOIN users ON doctors.user_id = users.id
#       LEFT JOIN treatments ON appointments.id = treatments.appointment_id
#       WHERE appointments.patient_id = ?
#       ORDER BY date DESC, time DESC
#    """, (session["user_id"],)).fetchall()

#     output = "<h2>Doctors</h2>"

#     for d in doctors:
#         output += f"""
#         <div style="margin-bottom:20px;">
#             <p><b>{d['name']}</b> ({d['specialization']})</p>
            
#             <form action="/book_appointment" method="POST">
#                 <input type="hidden" name="doctor_id" value="{d['id']}">
                
#                 Date: <input type="date" name="date" required>
#                 Time: <input type="time" name="time" required>
                
#                 <button type="submit">Book</button>
#             </form>
#         </div>
#         """
#     output += "<h2>Your Appointments</h2>"

#     for a in appointments:
#       status_color = {
#          "booked": "orange",
#          "completed": "green",
#          "cancelled": "red"
#       }.get(a['status'], "black")

#       output += f"""
#       <p>
#       Doctor: {a['doctor_name']} <br>
#       Date: {a['date']} | Time: {a['time']} <br>
#       Status: <span style='color:{status_color}'>{a['status']}</span><br>

#       Diagnosis: {a['diagnosis'] if a['diagnosis'] else 'N/A'} <br>
#       Prescription: {a['prescription'] if a['prescription'] else 'N/A'}
#       </p>
#     """

#     return render_template(
#       "patient_dashboard.html",
#       doctors=doctors,
#       appointments=appointments
#    )


# print("BOOK ROUTE LOADED")
# @app.route("/book_appointment", methods=["GET"])
# def book_appointment_get():
#     return "Use POST method"

# @app.route("/book_appointment", methods=["POST"])
# def book_appointment():

#     if "user_id" not in session or session.get("role") != "patient":
#         return redirect("/login")

#     doctor_id = request.form.get("doctor_id")
#     date = request.form.get("date")
#     time = request.form.get("time")

#     if not doctor_id or not date or not time:
#         return "All fields are required"

#     conn = get_db_connection()

#     # conflict check
#     existing = conn.execute("""
#         SELECT * FROM appointments 
#         WHERE doctor_id=? AND date=? AND time=? AND status!='cancelled'
#     """, (doctor_id, date, time)).fetchone()

#     if existing:
#         conn.close()
#         return "Slot already booked <br><a href='/patient_dashboard'>Go Back</a>"

#     # insert
#     conn.execute("""
#         INSERT INTO appointments (doctor_id, patient_id, date, time, status)
#         VALUES (?, ?, ?, ?, 'booked')
#     """, (doctor_id, session["user_id"], date, time))

#     conn.commit()
    
#     cache.pop("admin_stats", None)
#     conn.close()

#     #  TEMP SUCCESS RESPONSE
#     return "Appointment booked successfully <br><a href='/patient_dashboard'>Go Back</a>"

   

@app.route("/add_treatment/<int:app_id>", methods=["GET", "POST"])
def add_treatment(app_id):

    if "user_id" not in session or session.get("role") != "doctor":
        return redirect("/login")

    conn = get_db_connection()

    doctor = conn.execute("""
        SELECT id FROM doctors WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    if not doctor:
        conn.close()
        return "Doctor not found"

    appointment = conn.execute("""
        SELECT * FROM appointments 
        WHERE id=? AND doctor_id=?
    """, (app_id, doctor["id"])).fetchone()

    if not appointment:
        conn.close()
        return "Unauthorized"

    if request.method == "POST":
        diagnosis = request.form.get("diagnosis")
        prescription = request.form.get("prescription")
        notes = request.form.get("notes")

        conn.execute("""
            INSERT INTO treatments (appointment_id, diagnosis, prescription, notes)
            VALUES (?, ?, ?, ?)
        """, (app_id, diagnosis, prescription, notes))

        conn.execute("""
            UPDATE appointments SET status='completed' WHERE id=?
        """, (app_id,))

        conn.commit()
        conn.close()

        return redirect("/doctor_dashboard")

    conn.close()

    return render_template("add_treatment.html", app_id=app_id)


@app.route("/delete_appointment/<int:app_id>")
def delete_appointment(app_id):

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    conn = get_db_connection()
    conn.execute("DELETE FROM appointments WHERE id=?", (app_id,))
    conn.commit()
    conn.close()

    return redirect("/admin_dashboard")




@app.route("/api/doctors")
def api_doctors():

    conn = get_db_connection()

    doctors = conn.execute("""
        SELECT doctors.id, users.name, doctors.specialization, doctors.availability
        FROM doctors
        JOIN users ON doctors.user_id = users.id
        WHERE users.is_active=1
    """).fetchall()

    conn.close()

    return jsonify([dict(d) for d in doctors])



@app.route("/api/appointments")
def api_appointments():

    if "user_id" not in session or session.get("role") != "patient":
        return jsonify([])

    conn = get_db_connection()

    appointments = conn.execute("""
        SELECT appointments.*, users.name as doctor_name,
               treatments.diagnosis, treatments.prescription
        FROM appointments
        JOIN doctors ON appointments.doctor_id = doctors.id
        JOIN users ON doctors.user_id = users.id
        LEFT JOIN treatments ON appointments.id = treatments.appointment_id
        WHERE appointments.patient_id = ?
        ORDER BY date DESC, time DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return jsonify([dict(a) for a in appointments])




@app.route("/api/book", methods=["POST"])
def api_book():

    if "user_id" not in session or session.get("role") != "patient":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    doctor_id = data.get("doctor_id")
    date = data.get("date")
    time = data.get("time")

    # validation
    if not doctor_id or not date or not time:
        return jsonify({"error": "All fields are required"})

    doctor_id = int(doctor_id)

    from datetime import datetime
    selected_date = datetime.strptime(date, "%Y-%m-%d").date()

    if selected_date < datetime.now().date():
        return jsonify({"error": "Cannot book past date"})

    conn = get_db_connection()

    # conflict check
    existing = conn.execute("""
        SELECT * FROM appointments
        WHERE doctor_id=? AND date=? AND time=? AND status!='cancelled'
    """, (doctor_id, date, time)).fetchone()

    if existing:
        conn.close()
        return jsonify({"error": "Slot already booked"})

    #  insert
    conn.execute("""
        INSERT INTO appointments (doctor_id, patient_id, date, time, status)
        VALUES (?, ?, ?, ?, 'booked')
    """, (doctor_id, session["user_id"], date, time))

    conn.commit()
    conn.close()

    return jsonify({"message": "Booked successfully"})


@app.route("/set_availability", methods=["GET", "POST"])
def set_availability():

    if "user_id" not in session or session.get("role") != "doctor":
        return redirect("/login")

    conn = get_db_connection()

    doctor = conn.execute("""
        SELECT id FROM doctors WHERE user_id=?
    """, (session["user_id"],)).fetchone()

    if request.method == "POST":
        dates = []

        for i in range(1, 4):
            d = request.form.get(f"date{i}")
            if d:
                dates.append(d)

        availability = ",".join(dates)

        conn.execute("""
            UPDATE doctors SET availability=? WHERE id=?
        """, (availability, doctor["id"]))

        conn.commit()
        conn.close()

        return redirect("/doctor_dashboard")

    conn.close()
    return render_template("set_availability.html")


@app.route("/cancel_appointment/<int:app_id>")
def cancel_appointment(app_id):

    if "user_id" not in session or session.get("role") != "patient":
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()

    conn.execute("""
        UPDATE appointments
        SET status = 'cancelled'
        WHERE id = ? AND patient_id = ?
    """, (app_id, session["user_id"]))

    conn.commit()
    conn.close()

    return jsonify({"message": "Cancelled successfully"})




@app.route("/update_profile", methods=["POST"])
def update_profile():

    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    name = data.get("name")
    password = data.get("password")

    conn = get_db_connection()

    if name and name.strip():
        conn.execute("UPDATE users SET name=? WHERE id=?", (name, session["user_id"]))

    if password and password.strip():
        hashed = generate_password_hash(password)
        conn.execute("UPDATE users SET password=? WHERE id=?", (hashed, session["user_id"]))

    conn.commit()
    conn.close()

    return jsonify({"message": "Profile updated"})


@app.route("/patient_vue")
def patient_vue():
    return render_template("patient_vue.html")



# @app.route("/reset_user")
# def reset_user():
#     conn = get_db_connection()

#     hashed = generate_password_hash("123")

#     conn.execute("""
#         UPDATE users
#         SET password=?
#         WHERE email=?
#     """, (hashed, "kartik1@gmail.com"))

#     conn.commit()
#     conn.close()

#     return "Reset done with hash"


if __name__ == "__main__":
   init_db()

   app.run(debug=True)