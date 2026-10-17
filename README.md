# SmartMove — Smart Transport Tracking & Passenger Safety System

Flask + SQLite transport tracking prototype with Admin, Student and Driver dashboards. The 3D bus concept is not included.

## Features
- Admin dashboard with student/passenger management and an **Add Student** form
- Student dashboard with pickup point, attendance status, notifications and bus map
- Driver dashboard that can share device GPS coordinates with the server
- Live maps using Leaflet + OpenStreetMap tiles
- SQLite student, bus, notification and trip records
- Existing 30 demo students and 2 demo buses are retained

## Run on Windows
1. Install Python 3.10 or newer.
2. Extract this ZIP and open the `SmartMove_FINAL_FIXED` folder in VS Code.
3. Open Terminal in that folder and run:
   ```powershell
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   py app.py
   ```
4. Open `http://127.0.0.1:5000`.

## Demo account flow
- **Admin:** Choose Admin on the login screen. Use the dashboard's **Add Student** tab to create a student.
- **Student:** Select a student record from the list. New students appear in this list after they are added.
- **Driver:** Choose Driver and select the assigned bus. Open the driver page on the driver's phone and press **Start Live GPS**.

## Important GPS notes
- Browser GPS needs permission and a secure context. `localhost` works for development; a deployed website needs HTTPS.
- The driver page sends actual browser geolocation coordinates to Flask while the page is open. The admin and student dashboards read the latest saved bus location. This is a prototype, not a background tracker; mobile browser background behavior and device settings can affect updates.
- OpenStreetMap tiles require internet access and attribution.
- The existing demo login is role selection, not production authentication. Before real deployment, add passwords, proper user accounts, CSRF protection, authorization hardening, HTTPS, and a production WSGI server. Do not expose this prototype publicly with sensitive data.

## Soft Computing feature: fuzzy-logic ETA
- Added `fuzzy_eta.py`, a lightweight fuzzy inference estimator using overlapping distance and speed membership functions, IF-style rule activations, and a weighted output estimate.
- Student dashboard requests `/api/student/<student_id>/eta` and displays ETA to the student's pickup point, straight-line distance, inferred traffic band, speed band, and GPS source.
- The estimate uses the latest saved bus position and speed. Straight-line distance does not follow actual roads, so treat this as a prototype estimate rather than navigation-grade ETA.
- `fuzzy_eta_sample_dataset.csv` contains **synthetic illustrative examples only**, not collected real-world measurements and not training data. For an academic evaluation, record actual bus travel times and compare them with predictions.
- This implementation does not require an external dataset or an additional Python package.

## Suggested Soft Computing evaluation
1. Test near/medium/far distances and slow/normal/fast speeds.
2. Record predicted ETA alongside actual measured travel time for a set of trips.
3. Calculate MAE (mean absolute error) on held-out observations. Do not claim accuracy results until you collect and evaluate real observations.


## Live GPS and ETA notes (updated)

- The student page no longer presents a demo bus coordinate as a live bus location. It waits until the driver starts GPS sharing.
- Driver GPS updates include reported accuracy. Fixes worse than 200 metres are ignored and the driver is asked to wait for a better signal.
- Student ETA tries to request a real road route from the public OSRM routing demo service (no API key). The app caches the result briefly. If road routing is unavailable, it labels the result as a straight-line fallback, which is less accurate.
- ETA uses road-route duration plus the project's fuzzy speed/distance rules. This is still an approximate prototype, not guaranteed navigation or traffic-aware commercial routing. The public OSRM demo service is rate-limited and is not intended for production-scale use.
- Use real pickup-stop latitude/longitude in the admin student form. The preloaded sample stops are illustrative Nagpur coordinates and may not match your college's actual stops.
- For GPS, use the driver's phone, allow precise location, keep the driver page open, and use HTTPS when deployed. GPS accuracy can worsen indoors or in weak-signal areas.
