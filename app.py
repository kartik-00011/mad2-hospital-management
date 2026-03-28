from flask import Flask,request,redirect,session,render_template
import sqlite3
from datetime import datetime


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
      INSERT OR IGNORE INTO users(name , email, password, role)
      VALUES ('Admin','admin@gmail.com','admin123','admin')
   """)

   conn.commit()
   conn.close()



app = Flask(__name__)
app.secret_key = "supersecret123"

@app.route("/")
def home():
   return "Hospital Management System Running"


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

      if not user or user["password"] != password:
         return "Invalid Credentials"
      
      if user["is_active"]==0:
         return "Account Deactivated"
      
      session["user_id"] = user["id"]
      session["role"] = user["role"]

      if user["role"] == "admin":
         return redirect("/admin_dashboard")
      
      elif user["role"] == "doctor":
         return redirect("/doctor_dashboard")
      
      else :
         return redirect("/patient_dashboard")
   
   return """
   <form method = "POST">
      Email : <input name = "email"><br>
      Password : <input name = "password" type = "password"><br>
      <button type = "submit"> Login </button>
   """


#patient registration
@app.route("/register",methods = ["GET","POST"])
def register():
   if request.method=="POST":
      name = request.form["name"]
      email = request.form["email"]
      password = request.form["password"]

      conn = get_db_connection()

      conn.execute("""
         INSERT INTO users(name,email,password,role)
         VALUES(?,?,?,?)
         """, (name , email,password,"patient"))
      
      conn.commit()
      conn.close()

      return "Registration Successful"
   
   return """
      <form method = "POST">
         Name: <input name = "name"><br>
         Email: <input name = "email"><br>
         Password: <input name = "password" type = "password"><br>
         <button type = "submit"> Register </button>
      </form>
   """


@app.route("/add_doctor",methods=["GET","POST"])
def add_doctor():
   if "user_id" not in session or session.get("role")!="admin":
      return "Unauthorised access"
   
   if request.method=="POST":
      name = request.form["name"]
      email = request.form["email"]
      password = request.form["password"]
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
   
   return """
      <form method= "POST">
         Name: <input name = "name"><br>
         Email: <input name = "email"><br>
         Password: <input name = "password" type = "password"><br>
         Specialization: <input name = "specialization"><br>
         <button type = "submit"> Add Doctor </button>
      </form>
   """




@app.route("/admin_dashboard")
def admin_dashboard():
   return "Admin Dashboard"

@app.route("/doctor_dashboard")
def doctor_dashboard():
   
   if "user_id" not in session or session.get("role")!="doctor":
      return "Unauthorised"
   
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
   
   conn.close()

   return render_template("doctor_dashboard.html",appointments=appointments)



@app.route("/update_status/<int:app_id>/<status>")
def update_status(app_id,status):

   if "user_id" not in session or session.get("role")!="doctor":
      return "Unauthorised"
   
   conn = get_db_connection()

   conn.execute("""
      UPDATE appointments SET status = ? WHERE id = ?
      """,(status, app_id))
   
   conn.commit()
   conn.close()

   return redirect("/doctor_dashboard")



@app.route("/patient_dashboard")
def patient_dashboard():
   if "user_id" not in session or session.get("role")!="patient":
      return "Unauthorised access"
   
   conn = get_db_connection()

   doctors = conn.execute("""
      SELECT doctors.id, users.name , doctors.specialization
      FROM doctors
      JOIN users ON doctors.user_id = users.id
      """).fetchall()
   
   conn.close()

   output = "<h2>Doctors</h2>"

   for d in doctors:
      output += f"""
         <p>
            {d['name']} ({d['specialization']})
            <a href = "/book_appointment/{d['id']}">Book</a>
         </p>
      """
   
   return output



@app.route("/book_appointment/<int:doctor_id>")
def book_appointment(doctor_id):

   if "user_id" not in session or session.get('role')!='patient':
      return redirect('/login')
   
   conn = get_db_connection()

   # checking duplicate
   existing = conn.execute("""
      SELECT * FROM appointments
      WHERE doctor_id = ? AND patient_id = ? AND date=?
      """, (doctor_id,session["user_id"],datetime.now().strftime("%Y-%m-%d"))).fetchone()
   
   if existing:
      conn.close()
      return "You already booked today"
   
   conn.execute("""
      INSERT INTO appointments (doctor_id ,patient_id ,date ,time ,status)
      VALUES(?,?,?,?,?)
      """,(doctor_id,
          session["user_id"],
          datetime.now().strftime("%Y-%m-%d"),
          datetime.now().strftime("%H:%M"),
          "booked"
      ))
   conn.commit()
   conn.close()

   return "Appointment booked"



if __name__ == "__main__":
   init_db()

   app.run(debug=True)