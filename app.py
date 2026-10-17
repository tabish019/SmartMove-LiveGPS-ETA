from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import sqlite3, os, math, random, json, urllib.request, urllib.error, time
from datetime import datetime
from fuzzy_eta import fuzzy_eta

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "transport.db")
# Public OSRM demo routing service: no API key required. Use politely and cache routes.
_route_cache = {}
def road_route(start_lat, start_lng, end_lat, end_lng):
    key = tuple(round(float(v), 4) for v in (start_lat, start_lng, end_lat, end_lng))
    now = time.time()
    cached = _route_cache.get(key)
    if cached and now - cached[0] < 30:
        return cached[1]
    url = ("https://router.project-osrm.org/route/v1/driving/"
           f"{start_lng},{start_lat};{end_lng},{end_lat}?overview=full&geometries=geojson&steps=false")
    req = urllib.request.Request(url, headers={"User-Agent": "SmartMoveCollegeProject/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        route = payload.get("routes", [])[0]
        result = {"distance_km": route["distance"] / 1000.0,
                  "duration_minutes": route["duration"] / 60.0,
                  "geometry": [[lat, lng] for lng, lat in route["geometry"]["coordinates"]],
                  "route_source": "Road route (OSRM)"}
        _route_cache[key] = (now, result)
        return result
    except Exception:
        return None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart-transport-demo-key")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS students(
      id INTEGER PRIMARY KEY, name TEXT, phone TEXT, pickup TEXT, lat REAL, lng REAL,
      route TEXT, status TEXT DEFAULT 'Expected', message TEXT DEFAULT '', boarded INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS buses(
      id INTEGER PRIMARY KEY, number TEXT, driver TEXT, lat REAL, lng REAL,
      route TEXT, status TEXT DEFAULT 'On Route', speed REAL DEFAULT 32, eta INTEGER DEFAULT 8,
      gps_updated_at TEXT DEFAULT '', gps_source TEXT DEFAULT 'Demo location'
    );
    CREATE TABLE IF NOT EXISTS notifications(
      id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, title TEXT, body TEXT,
      type TEXT, created_at TEXT, read INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS trips(
      id INTEGER PRIMARY KEY AUTOINCREMENT, bus_id INTEGER, event TEXT, detail TEXT, created_at TEXT
    );
    """)
    # Upgrade older databases without deleting existing student or bus records.
    bus_cols = {row[1] for row in conn.execute("PRAGMA table_info(buses)").fetchall()}
    if "gps_updated_at" not in bus_cols:
        conn.execute("ALTER TABLE buses ADD COLUMN gps_updated_at TEXT DEFAULT ''")
    if "gps_source" not in bus_cols:
        conn.execute("ALTER TABLE buses ADD COLUMN gps_source TEXT DEFAULT 'Demo location'")
    if "gps_accuracy" not in bus_cols:
        conn.execute("ALTER TABLE buses ADD COLUMN gps_accuracy REAL DEFAULT NULL")
    count = conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
    if count == 0:
        names = ["Aarav Sharma","Aditi Patil","Ananya Joshi","Arjun Mehta","Diya Shah",
                 "Ishaan Kulkarni","Kavya Singh","Manav Jain","Meera Deshmukh","Neha Gupta",
                 "Omkar Pawar","Pranav Nair","Riya Kapoor","Rohan Verma","Sakshi More",
                 "Samar Khan","Shreya Iyer","Tanvi Rao","Vedant Mishra","Yash Thakur",
                 "Zoya Khan","Advik Bhosale","Ira Chavan","Kabir Soni","Mahi Joshi",
                 "Nikhil Jadhav","Pooja Rane","Rahul Shetty","Simran Kaur","Vansh Agrawal"]
        places = [
          ("Campus Gate",21.1467,79.0882),("Sadar",21.1535,79.0808),("Dharampeth",21.1350,79.0715),
          ("Manish Nagar",21.1138,79.0671),("Pratap Nagar",21.1274,79.0650),("Wardha Road",21.1110,79.0812),
          ("Trimurti Nagar",21.1238,79.0456),("Besa",21.0782,79.0789),("Somalwada",21.1117,79.0852),
          ("Hingna",21.1077,78.9981),("Civil Lines",21.1545,79.0718),("Mahal",21.1427,79.1021),
          ("Nandanvan",21.1392,79.1178),("Jaripatka",21.1775,79.0932),("Wadi",21.1450,78.9950)]
        for i,n in enumerate(names):
            place = places[i % len(places)]
            conn.execute("INSERT INTO students(name,phone,pickup,lat,lng,route,status) VALUES(?,?,?,?,?,?,?)",
                         (n,f"+91 98{10000000+i}",place[0],place[1],place[2],"Route A" if i<15 else "Route B",
                          "Expected"))
    bcount = conn.execute("SELECT COUNT(*) c FROM buses").fetchone()["c"]
    if bcount == 0:
        conn.execute("INSERT INTO buses(number,driver,lat,lng,route,speed,eta) VALUES(?,?,?,?,?,?,?)",
                     ("ST-01","Rajesh Patil",21.1315,79.0750,"Route A",34,7))
        conn.execute("INSERT INTO buses(number,driver,lat,lng,route,speed,eta) VALUES(?,?,?,?,?,?,?)",
                     ("ST-02","Suresh More",21.1570,79.0910,"Route B",29,11))
    conn.commit(); conn.close()

@app.route("/")
def home():
    role = session.get("role")
    if role == "admin": return redirect(url_for("admin"))
    if role == "student": return redirect(url_for("student"))
    if role == "driver": return redirect(url_for("driver"))
    return render_template("login.html")

@app.get("/api/login-options")
def login_options():
    conn = db()
    students = [dict(x) for x in conn.execute("SELECT id,name FROM students ORDER BY id").fetchall()]
    buses = [dict(x) for x in conn.execute("SELECT id,number,driver,route FROM buses ORDER BY id").fetchall()]
    conn.close()
    return jsonify({"students": students, "buses": buses})

@app.post("/login")
def login():
    role = request.form.get("role", "student")
    session.clear()
    if role == "admin":
        session["role"] = "admin"
        return redirect(url_for("admin"))
    if role == "driver":
        try: bus_id = int(request.form.get("bus_id", "1"))
        except ValueError: return redirect(url_for("home"))
        conn = db(); bus = conn.execute("SELECT id FROM buses WHERE id=?", (bus_id,)).fetchone(); conn.close()
        if not bus: return redirect(url_for("home"))
        session["role"] = "driver"; session["bus_id"] = bus_id
        return redirect(url_for("driver"))
    try: student_id = int(request.form.get("student_id", "1"))
    except ValueError: return redirect(url_for("home"))
    conn = db(); student = conn.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone(); conn.close()
    if not student: return redirect(url_for("home"))
    session["role"] = "student"; session["student_id"] = student_id
    return redirect(url_for("student"))

@app.get("/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.route("/admin")
def admin():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("admin.html")

@app.route("/student")
def student():
    if session.get("role") != "student": return redirect(url_for("home"))
    return render_template("student.html", student_id=session.get("student_id",1))

@app.route("/driver")
def driver():
    if session.get("role") != "driver": return redirect(url_for("home"))
    conn = db(); bus = conn.execute("SELECT * FROM buses WHERE id=?", (session.get("bus_id"),)).fetchone(); conn.close()
    if not bus:
        session.clear(); return redirect(url_for("home"))
    return render_template("driver.html", bus=dict(bus))

@app.get("/api/driver/bus")
def driver_bus():
    if session.get("role") != "driver": return jsonify({"error":"Driver login required"}), 401
    conn=db(); bus=conn.execute("SELECT * FROM buses WHERE id=?",(session.get("bus_id"),)).fetchone(); conn.close()
    return jsonify(dict(bus) if bus else {}), (200 if bus else 404)

@app.post("/api/driver/location")
def driver_location():
    if session.get("role") != "driver": return jsonify({"ok":False,"error":"Driver login required"}), 401
    data=request.get_json(silent=True) or {}
    try:
        lat=float(data.get("lat")); lng=float(data.get("lng"))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180): raise ValueError()
    except (TypeError, ValueError): return jsonify({"ok":False,"error":"Valid latitude and longitude are required"}), 400
    bid=session.get("bus_id"); now=datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
    conn=db(); bus=conn.execute("SELECT * FROM buses WHERE id=?",(bid,)).fetchone()
    if not bus: conn.close(); return jsonify({"ok":False,"error":"Bus not found"}),404
    speed=float(data.get("speed") or 0) * 3.6
    speed=max(0,min(160,speed))
    try: accuracy=float(data.get("accuracy") or 9999)
    except (TypeError, ValueError): accuracy=9999
    # Ignore extremely poor fixes so a GPS jump does not move the bus across the map.
    if accuracy > 200:
        conn.close()
        return jsonify({"ok":False,"error":f"GPS accuracy is too low ({accuracy:.0f} m). Move outdoors and wait for a better signal."}), 422
    conn.execute("UPDATE buses SET lat=?,lng=?,speed=?,gps_updated_at=?,gps_source='Driver GPS',gps_accuracy=? WHERE id=?",(lat,lng,speed,now,accuracy,bid))
    conn.execute("INSERT INTO trips(bus_id,event,detail,created_at) VALUES(?,?,?,?)",(bid,"Driver GPS update",f"Real GPS location {lat:.6f}, {lng:.6f}",now))
    conn.commit(); updated=dict(conn.execute("SELECT * FROM buses WHERE id=?",(bid,)).fetchone()); conn.close()
    return jsonify({"ok":True,"bus":updated,"updated_at":now})

@app.get("/api/dashboard")
def dashboard():
    conn=db()
    students=[dict(x) for x in conn.execute("SELECT * FROM students ORDER BY id").fetchall()]
    buses=[dict(x) for x in conn.execute("SELECT * FROM buses ORDER BY id").fetchall()]
    notifications=[dict(x) for x in conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 12").fetchall()]
    trips=[dict(x) for x in conn.execute("SELECT * FROM trips ORDER BY id DESC LIMIT 15").fetchall()]
    conn.close()
    return jsonify({"students":students,"buses":buses,"notifications":notifications,"trips":trips})

@app.get("/api/student/<int:sid>/eta")
def student_eta(sid):
    """Estimate arrival using a road route where available, then fuzzy speed rules."""
    conn = db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not student:
        conn.close(); return jsonify({"error": "Student not found"}), 404
    bus = conn.execute("SELECT * FROM buses WHERE route=? ORDER BY id LIMIT 1", (student["route"],)).fetchone()
    conn.close()
    if not bus: return jsonify({"error": "No bus is assigned to this route"}), 404
    if student["lat"] is None or student["lng"] is None:
        return jsonify({"error": "This pickup stop has no coordinates. Ask admin to add the stop latitude and longitude."}), 422
    gps_time = bus["gps_updated_at"] or ""
    live = bool(gps_time and bus["gps_source"] == "Driver GPS")
    if not live:
        return jsonify({"live_gps":False,"error":"Waiting for the driver to start live GPS. The map currently has a sample location, not the bus's real position.",
                        "bus_number":bus["number"],"gps_source":bus["gps_source"] or "Demo location",
                        "gps_updated_at":"No live GPS received yet"})
    # Warn instead of presenting an old GPS fix as the current location.
    try:
        from datetime import datetime
        stamp=datetime.strptime(gps_time, "%d %b %Y, %I:%M:%S %p")
        age_seconds=(datetime.now()-stamp).total_seconds()
    except Exception: age_seconds=9999
    if age_seconds > 90:
        return jsonify({"live_gps":False,"stale":True,"error":"Driver GPS is stale. Ask the driver to reopen GPS sharing.",
                        "gps_updated_at":gps_time,"gps_source":"Driver GPS","bus_number":bus["number"]})
    route=road_route(bus["lat"],bus["lng"],student["lat"],student["lng"])
    # Straight-line distance is retained only as an explicitly labelled fallback if routing is unavailable.
    lat1,lon1,lat2,lon2=map(math.radians,[bus["lat"],bus["lng"],student["lat"],student["lng"]])
    dlat,dlon=lat2-lat1,lon2-lon1
    a=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    straight_km=6371.0*2*math.asin(min(1.0,math.sqrt(a)))
    if route:
        distance_km=route["distance_km"]
        # Fuzzy rules remain part of the Soft Computing component. Blend them with road-route duration.
        fuzzy=fuzzy_eta(distance_km, bus["speed"] or 0)
        road_minutes=max(1.0, route["duration_minutes"])
        speed=float(bus["speed"] or 0)
        traffic_factor=1.25 if speed < 10 else (1.12 if speed < 20 else (1.0 if speed < 35 else 0.92))
        eta=max(1, int(round(0.7*road_minutes*traffic_factor + 0.3*fuzzy["eta_minutes"])))
        geometry=route["geometry"]
        route_source=route["route_source"]
    else:
        distance_km=straight_km
        fuzzy=fuzzy_eta(distance_km,bus["speed"] or 0)
        eta=fuzzy["eta_minutes"]
        geometry=[]
        route_source="Straight-line fallback (road routing unavailable; ETA less accurate)"
    return jsonify({"live_gps":True,"eta_minutes":eta,"distance_km":round(distance_km,2),
                    "straight_line_km":round(straight_km,2),"speed_kmh":round(float(bus["speed"] or 0),1),
                    "traffic":fuzzy["traffic"],"speed_band":fuzzy["speed_band"],"method":"Fuzzy ETA + road-route duration",
                    "bus_number":bus["number"],"gps_source":bus["gps_source"],"gps_updated_at":gps_time,
                    "gps_accuracy":bus["gps_accuracy"],"route_source":route_source,"route_geometry":geometry})

@app.post("/api/students")
def add_student():
    if session.get("role") != "admin": return jsonify({"error":"Admin login required"}), 401
    data=request.get_json(silent=True) or {}
    name=str(data.get("name", "")).strip(); phone=str(data.get("phone", "")).strip()
    pickup=str(data.get("pickup", "")).strip(); route=str(data.get("route", "Route A")).strip()
    if not name or not pickup or route not in ("Route A", "Route B"):
        return jsonify({"error":"Name, pickup point and a valid route are required"}),400
    try:
        lat=float(data.get("lat")) if str(data.get("lat", "")).strip() else None
        lng=float(data.get("lng")) if str(data.get("lng", "")).strip() else None
        if lat is not None and not -90 <= lat <= 90: raise ValueError()
        if lng is not None and not -180 <= lng <= 180: raise ValueError()
    except (TypeError,ValueError): return jsonify({"error":"Latitude/longitude must be valid coordinates"}),400
    conn=db(); cur=conn.execute("INSERT INTO students(name,phone,pickup,lat,lng,route,status,message,boarded) VALUES(?,?,?,?,?,?, 'Expected','',0)",(name,phone,pickup,lat,lng,route))
    sid=cur.lastrowid
    now=datetime.now().strftime("%d %b %Y, %I:%M %p")
    conn.execute("INSERT INTO trips(bus_id,event,detail,created_at) VALUES(?,?,?,?)",(1,"Student added",f"New student STU-{sid:03d}: {name}",now))
    conn.commit(); student=dict(conn.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()); conn.close()
    return jsonify({"ok":True,"student":student}),201

@app.get("/api/student/<int:sid>")
def student_data(sid):
    conn=db()
    s=conn.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()
    buses=conn.execute("SELECT * FROM buses WHERE route=?",(s["route"],)).fetchall() if s else []
    notes=conn.execute("SELECT * FROM notifications WHERE student_id=? OR student_id IS NULL ORDER BY id DESC LIMIT 10",(sid,)).fetchall()
    conn.close()
    return jsonify({"student":dict(s) if s else None,"buses":[dict(x) for x in buses],"notifications":[dict(x) for x in notes]})

@app.post("/api/student/<int:sid>/status")
def status(sid):
    data=request.get_json() or {}
    st=data.get("status","Not Coming")
    msg=data.get("message","")
    conn=db()
    conn.execute("UPDATE students SET status=?, message=?, boarded=? WHERE id=?",
                 (st,msg,1 if st=="Boarded" else 0,sid))
    title="Passenger status updated"
    body=f"Student #{sid} marked {st}. {msg}".strip()
    conn.execute("INSERT INTO notifications(student_id,title,body,type,created_at) VALUES(?,?,?,?,?)",
                 (sid,title,body,"attendance",datetime.now().strftime("%d %b %Y, %I:%M %p")))
    conn.execute("INSERT INTO trips(bus_id,event,detail,created_at) VALUES(?,?,?,?)",
                 (1,"Attendance update",body,datetime.now().strftime("%d %b %Y, %I:%M %p")))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.post("/api/notification")
def notification():
    data=request.get_json() or {}
    conn=db()
    conn.execute("INSERT INTO notifications(student_id,title,body,type,created_at) VALUES(?,?,?,?,?)",
                 (data.get("student_id"),data.get("title","Transport alert"),data.get("body",""),data.get("type","info"),
                  datetime.now().strftime("%d %b %Y, %I:%M %p")))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.post("/api/bus/<int:bid>/move")
def move_bus(bid):
    conn=db()
    b=conn.execute("SELECT * FROM buses WHERE id=?",(bid,)).fetchone()
    if not b: return jsonify({"ok":False}),404
    # Legacy demo endpoint retained for compatibility. Real driver GPS updates
    # are posted to /api/driver/location and are not simulated by the UI.
    target_lat,target_lng=21.1467,79.0882
    lat=b["lat"]+(target_lat-b["lat"])*0.025+random.uniform(-0.0007,0.0007)
    lng=b["lng"]+(target_lng-b["lng"])*0.025+random.uniform(-0.0007,0.0007)
    speed=max(8,min(48,b["speed"]+random.uniform(-3,3)))
    eta=max(2,int(b["eta"]-0.3))
    conn.execute("UPDATE buses SET lat=?,lng=?,speed=?,eta=? WHERE id=?",(lat,lng,speed,eta,bid))
    conn.execute("INSERT INTO trips(bus_id,event,detail,created_at) VALUES(?,?,?,?)",
                 (bid,"GPS update",f"Location {lat:.5f}, {lng:.5f} | {speed:.0f} km/h",
                  datetime.now().strftime("%d %b %Y, %I:%M %p")))
    conn.commit()
    bus=dict(conn.execute("SELECT * FROM buses WHERE id=?",(bid,)).fetchone())
    conn.close()
    return jsonify(bus)

@app.post("/api/student/<int:sid>/remind")
def remind(sid):
    conn=db()
    s=conn.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()
    if s:
        conn.execute("INSERT INTO notifications(student_id,title,body,type,created_at) VALUES(?,?,?,?,?)",
                     (sid,"Bus approaching",f"Your bus is approaching {s['pickup']}. Please be ready.",
                      "approach",datetime.now().strftime("%d %b %Y, %I:%M %p")))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

init_db()
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
