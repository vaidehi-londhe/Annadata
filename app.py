import sqlite3
import random
import psycopg2
import requests
from psycopg2.extras import RealDictCursor
import os
from datetime import timedelta, date
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI
client = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)


DATABASE = 'annadata.db'

# ---------------------------------------------------------
# Database helpers
# ---------------------------------------------------------

class PostgresDB:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        # Convert SQLite placeholders (?) to PostgreSQL (%s)
        query = query.replace("?", "%s")

        cursor = self.connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)
        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def get_db():
    db = getattr(g, '_database', None)

    if db is None:
        connection = psycopg2.connect(
            host="aws-0-ap-northeast-2.pooler.supabase.com",
            port=5432,
            database="postgres",
            user="postgres.ujiavoxmwdwjbfdgizhc",
            password=os.environ["SUPABASE_DB_PASSWORD"]
        )

        db = g._database = PostgresDB(connection)

    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.commit()
        

def seed_data(db):
    existing = db.execute("SELECT COUNT(*) as c FROM schemes").fetchone()['c']
    if existing == 0:
        schemes = [
            ("PM-KISAN", "Income Support",
             "A direct income support scheme providing financial assistance to eligible farmer families across the country.",
             "₹6,000/year|Paid in 3 installments of ₹2,000|Direct bank transfer",
             "Land holding: any size|All farmer families with cultivable land",
             "Aadhaar card|Bank passbook|Land ownership papers",
             "Visit official portal|Register with Aadhaar|Submit land details",
             "https://pmkisan.gov.in", 0, 999),
            ("PMFBY", "Insurance",
             "Crop insurance scheme protecting farmers against yield loss due to natural calamities, pests, and diseases.",
             "Low premium crop insurance|Covers pre-sowing to post-harvest losses",
             "All farmers growing notified crops|Both loanee and non-loanee farmers",
             "Aadhaar card|Land records|Bank account details",
             "Apply through bank or CSC|Choose notified crop and area|Pay premium before cutoff",
             "https://pmfby.gov.in", 0, 999),
            ("Kisan Credit Card", "Credit & Loans",
             "Provides farmers with timely access to credit for crop production and allied activities at low interest rates.",
             "Low-interest loans|Flexible repayment|Covers crop and allied needs",
             "Any farmer, tenant farmer, or sharecropper|Land documents required",
             "Aadhaar card|Land documents|Passport size photo",
             "Visit nearest bank branch|Fill KCC application|Submit land proof",
             "https://www.myscheme.gov.in/schemes/kcc", 0, 999),
            ("Per Drop More Crop", "Irrigation",
             "Subsidy support for drip and sprinkler irrigation systems to improve water use efficiency.",
             "Up to 55% subsidy for small farmers|Up to 45% for other farmers",
             "Any farmer investing in micro-irrigation",
             "Aadhaar card|Land records|Water source proof",
             "Apply via state agriculture portal|Get technical approval|Install and claim subsidy",
             "https://pmksy.gov.in", 0, 999),
            ("Soil Health Card Scheme", "Farming Support",
             "Provides farmers with soil nutrient status and fertilizer recommendations for their land.",
             "Free soil testing|Crop-wise nutrient recommendations",
             "All farmers with cultivable land",
             "Land ownership proof|Aadhaar card",
             "Contact local agriculture office|Submit soil sample|Receive card in 3-4 weeks",
             "https://soilhealth.dac.gov.in", 0, 999),
        ]
        db.executemany('''INSERT INTO schemes
            (name, category, overview, benefits, eligibility, documents, how_to_apply, official_link, min_income_lakh, max_income_lakh)
            VALUES (?,?,?,?,?,?,?,?,?,?)''', schemes)

        crops = [
            ("Rice", "Loamy", "High", "Kharif", 120, "Fits monsoon + loamy soil"),
            ("Maize", "Loamy", "Medium", "Kharif", 90, "Moderate water needs"),
            ("Soybean", "Loamy", "Medium", "Kharif", 100, "Lower water dependency"),
            ("Cotton", "Black soil", "Medium", "Kharif", 160, "Good for Kharif season, moderate water needs"),
            ("Wheat", "Loamy", "Medium", "Rabi", 120, "Suited to winter season and loamy soil"),
            ("Mustard", "Sandy", "Low", "Rabi", 100, "Low water crop for winter season"),
        ]
        db.executemany('''INSERT INTO crops
            (name, soil_type, water_need, season, duration_days, reason)
            VALUES (?,?,?,?,?,?)''', crops)
        db.commit()

def add_extra_crops(db):
    extra_crops = [
        ("Bajra", "Sandy", "Low", "Kharif", 85, "Drought-resistant crop with low water needs"),
        ("Jowar", "Black soil", "Low", "Kharif", 110, "Suitable for dry regions and black soil"),
        ("Groundnut", "Sandy", "Medium", "Kharif", 120, "Good oilseed crop for sandy soil"),
        ("Sugarcane", "Loamy", "High", "Kharif", 365, "High-water commercial crop for fertile land"),
        ("Tur", "Black soil", "Low", "Kharif", 150, "Pulse crop suitable for moderate rainfall"),
        ("Moong", "Sandy", "Low", "Zaid", 65, "Fast-growing summer pulse with low water need"),
        ("Tomato", "Loamy", "Medium", "Zaid", 90, "Vegetable crop for well-drained loamy soil"),
        ("Potato", "Loamy", "Medium", "Rabi", 110, "Winter crop that grows well in loamy soil"),
        ("Chana", "Black soil", "Low", "Rabi", 120, "Low-water pulse crop for winter season"),
        ("Onion", "Loamy", "Medium", "Rabi", 130, "Popular vegetable crop for cool weather"),
        ("Sunflower", "Loamy", "Medium", "Rabi", 100, "Oilseed crop with moderate water needs"),
        ("Watermelon", "Sandy", "Medium", "Zaid", 90, "Summer fruit crop suited to sandy soil"),
    ]

    for crop in extra_crops:
        already_exists = db.execute(
            "SELECT id FROM crops WHERE name=?",
            (crop[0],)
        ).fetchone()

        if not already_exists:
            db.execute(
                """
                INSERT INTO crops
                (name, soil_type, water_need, season, duration_days, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                crop
            )

    db.commit()
    


TIPS = [
    "Rotate crops each season to keep your soil healthy and reduce pest buildup.",
    "Apply for PM-KISAN before the registration deadline to avoid missing your installment.",
    "Test your soil's pH before choosing a new crop — it can save you a failed harvest.",
    "Drip irrigation can cut your water usage by up to 40% compared to flood irrigation.",
    "Store your seeds in a cool, dry place to protect them before the next sowing season.",
]

DISTRESS_KEYWORDS = [
    "no way out", "can't go on", "end it", "give up", "no hope",
    "worthless", "burden", "hopeless", "can't take it", "suicide", "kill myself","mujhe nahi jeena", "mujhe nhi jeena", "jeena nahi hai",
    "marna chahta", "marna chahti", "khud ko khatam","kill","die"
]

HELPLINES = {
    "kiran": {"name": "KIRAN Helpline", "number": "1800-599-0019"},
    "tele_manas": {"name": "Tele-MANAS", "number": "14416"},
}


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

FARM_GUIDE = {
    "rice": [
        ("moisture", "Check soil moisture", "Rice grows best when the soil stays moist."),
        ("pests", "Inspect leaves for pests", "Look for yellow leaves, insects, or damaged plants.")
    ],

    "wheat": [
        ("irrigate", "Check soil moisture", "Wheat needs timely watering during growth."),
        ("weeds", "Check for weeds", "Remove weeds before they spread.")
    ],

    "cotton": [
        ("pests", "Inspect cotton plants", "Check flowers and leaves for pest damage."),
        ("moisture", "Check soil moisture", "Avoid overwatering cotton plants.")
    ],

    "sugarcane": [
        ("moisture", "Check soil moisture", "Sugarcane needs regular moisture during growth."),
        ("weeds", "Remove nearby weeds", "Weeds take water and nutrients from sugarcane."),
        ("pests", "Inspect leaves and stem", "Check for holes, damaged leaves, or pests.")
    ],

    "maize": [
        ("irrigate", "Check if maize needs water", "Water only if the top soil feels dry."),
        ("pests", "Inspect leaves for pests", "Check leaves and stem for insect damage.")
    ],

    "onion": [
        ("moisture", "Check soil moisture", "Onion needs regular but controlled watering."),
        ("weeds", "Remove nearby weeds", "Keep the soil around onion plants clear of weeds.")
    ],

    "other": [
        ("check", "Inspect your crop", "Check leaves, soil moisture, and signs of pests."),
        ("weeds", "Check for weeds", "Remove weeds around your crop when needed.")
    ]
}


def get_task_info(task_key):
    crop_name, task_id = task_key.rsplit("-", 1)

    for item_id, title, reason in FARM_GUIDE.get(crop_name, []):
        if item_id == task_id:
            return {
                "crop": crop_name.title(),
                "title": title,
                "reason": reason
            }

    return None

# ---------------------------------------------------------
# Auth routes
# ---------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('splash'))


@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')


@app.route('/api/notifications/schemes')
@login_required
def api_notification_schemes():
    db = get_db()
    latest = db.execute(
        "SELECT id, name, category, overview FROM schemes ORDER BY id DESC LIMIT 5"
    ).fetchall()
    return jsonify([{
        'id': s['id'],
        'name': s['name'],
        'category': s['category'],
        'overview': s['overview']
    } for s in latest])
    
    

@app.route('/saved-schemes')
@login_required
def saved_schemes():
    db = get_db()

    saved = db.execute("""
        SELECT
            s.id,
            s.name,
            s.category,
            s.overview,
            s.benefits,
            s.official_link
        FROM saved_schemes ss
        JOIN schemes s ON s.id = ss.scheme_id
        WHERE ss.user_id = ?
        ORDER BY ss.saved_at DESC
    """, (session['user_id'],)).fetchall()

    return render_template(
        'saved_schemes.html',
        saved=saved
    )
    
    
@app.route('/splash')
def splash():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('splash.html')


@app.route('/farm-planner')
@login_required
def farm():
    db = get_db()

    profile = db.execute(
        "SELECT currently_growing FROM farmer_profile WHERE user_id=?",
        (session['user_id'],)
    ).fetchone()

    crops = []

    if profile and profile['currently_growing']:
        crops = [
            crop.strip().lower()
            for crop in profile['currently_growing'].split(',')
        ]

    today = date.today().isoformat()

    actions = {
        row['task_key']: row
        for row in db.execute(
            "SELECT * FROM farm_task_actions WHERE user_id=?",
            (session['user_id'],)
        ).fetchall()
    }

    completed = []

    for task_key, action in actions.items():
        if action['status'] == 'done':
            task = get_task_info(task_key)

            if task:
                completed.append(task)

    suggestions = []

    for crop in crops:
        for task_id, title, reason in FARM_GUIDE.get(crop, []):
            task_key = f"{crop}-{task_id}"
            action = actions.get(task_key)

            if action and action['status'] == 'done':
                continue

            if action and action['remind_on'] and action['remind_on'] > today:
                continue

            suggestions.append({
                "task_key": task_key,
                "crop": crop.title(),
                "title": title,
                "reason": reason
            })

    return render_template(
        'farm.html',
        suggestions=suggestions[:3],
        crops=crops,
        completed=completed
    )


@app.route('/farm-planner/action', methods=['POST'])
@login_required
def farm_action():
    task_key = request.form.get('task_key')
    action = request.form.get('action')

    db = get_db()

    if action == 'done':
        status = 'done'
        remind_on = None
    else:
        status = 'remind_later'
        remind_on = (date.today() + timedelta(days=1)).isoformat()

    db.execute("""
        INSERT INTO farm_task_actions (user_id, task_key, status, remind_on)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, task_key)
        DO UPDATE SET
            status=excluded.status,
            remind_on=excluded.remind_on,
            updated_at=CURRENT_TIMESTAMP
    """, (session['user_id'], task_key, status, remind_on))

    db.commit()
    return redirect(url_for('farm'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        error = None
        if not full_name or not phone or not password:
            error = "Please fill in all fields."
        elif len(phone) != 10 or not phone.isdigit():
            error = "Enter a valid 10-digit mobile number."
        elif password != confirm:
            error = "Passwords do not match."

        db = get_db()
        if error is None:
            existing = db.execute("SELECT id FROM users WHERE phone_number=?", (phone,)).fetchone()
            if existing:
                error = "An account with this number already exists."

        if error:
            return render_template('signup.html', error=error)

        password_hash = generate_password_hash(password)
        cur = db.execute(
            "INSERT INTO users (full_name, phone_number, password_hash) VALUES (?,?,?)",
            (full_name, phone, password_hash)
        )
        db.commit()
        user_id = cur.lastrowid

        # Auto-login after signup
        session.permanent = True
        session['user_id'] = user_id
        session['full_name'] = full_name
        return redirect(url_for('profile_setup'))

    return render_template('signup.html', error=None)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE phone_number=?", (phone,)).fetchone()

        if user is None or not check_password_hash(user['password_hash'], password):
            return render_template('login.html', error="Invalid phone number or password.")

        session.permanent = True
        session['user_id'] = user['id']
        session['full_name'] = user['full_name']

        profile = db.execute("SELECT id FROM farmer_profile WHERE user_id=?", (user['id'],)).fetchone()
        if profile is None:
            return redirect(url_for('profile_setup'))
        return redirect(url_for('dashboard'))

    return render_template('login.html', error=None)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error = None
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE phone_number=?", (phone,)).fetchone()

        if not user:
            error = "No account found with this mobile number."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            password_hash = generate_password_hash(password)
            db.execute("UPDATE users SET password_hash=? WHERE phone_number=?", (password_hash, phone))
            db.commit()
            return redirect(url_for('login'))

    return render_template('forgot_password.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('splash'))


def weather_code_to_text(code):
    mapping = {
        0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
        45: "Fog", 48: "Fog",
        51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
        61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
        71: "Light Snow", 80: "Rain Showers", 81: "Rain Showers",
        95: "Thunderstorm"
    }
    return mapping.get(code, "Variable")


@app.route('/api/weather')
@login_required
def api_weather():
    db = get_db()
    profile = db.execute(
        "SELECT state, district FROM farmer_profile WHERE user_id=?",
        (session['user_id'],)
    ).fetchone()

    location = (profile['district'] if profile and profile['district'] else None) \
        or (profile['state'] if profile and profile['state'] else None) \
        or "Mumbai"

    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "country": "IN"},
            timeout=5
        ).json()

        if not geo.get("results"):
            return jsonify({"error": "Location not found"}), 404

        lat = geo["results"][0]["latitude"]
        lon = geo["results"][0]["longitude"]
        place_name = geo["results"][0]["name"]
        
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "daily": "precipitation_probability_max,temperature_2m_max,weather_code",
                "timezone": "auto",
                "forecast_days": 5
            },
            timeout=5
        ).json()

        current_temp = weather["current"]["temperature_2m"]
        current_code = weather["current"]["weather_code"]
        rain_chance_tomorrow = weather["daily"]["precipitation_probability_max"][1]
        max_temp_today = weather["daily"]["temperature_2m_max"][0]

        alert = None
        if rain_chance_tomorrow >= 60:
            alert = f"Rain likely tomorrow ({rain_chance_tomorrow}% chance) — avoid spraying pesticides today."
        elif max_temp_today >= 40:
            alert = "Extreme heat expected today — ensure adequate irrigation for your crops."
            
        import datetime as dt
        forecast = []
        daily_dates = weather["daily"]["time"]
        daily_temps = weather["daily"]["temperature_2m_max"]
        daily_codes = weather["daily"]["weather_code"]

        for i in range(1, 5):
            day_name = dt.datetime.strptime(daily_dates[i], "%Y-%m-%d").strftime("%a")
            forecast.append({
                "day": day_name,
                "temp": round(daily_temps[i]),
                "condition": weather_code_to_text(daily_codes[i])
            })
            
        return jsonify({
            "location": place_name,
            "temp": round(current_temp),
            "condition": weather_code_to_text(current_code),
            "alert": alert,
            "forecast": forecast
        })
    except Exception:
        return jsonify({"error": "Could not fetch weather"}), 500

# ---------------------------------------------------------
# Profile setup + dashboard
# ---------------------------------------------------------

@app.route('/profile-setup', methods=['GET', 'POST'])
@login_required
def profile_setup():

    db = get_db()

    # Get existing profile for this logged-in user
    existing_profile = db.execute(
        "SELECT * FROM farmer_profile WHERE user_id=?",
        (session['user_id'],)
    ).fetchone()

    if request.method == 'POST':

        state = request.form.get('state')
        district = request.form.get('district')
        village = request.form.get('village')

        land_size = request.form.get('land_size')
        land_unit = request.form.get('land_unit', 'acres')

        income_range = request.form.get('income_range')
        experience = request.form.get('experience')

        crops = ','.join(request.form.getlist('crops'))

        # --------------------------------
        # UPDATE existing profile
        # --------------------------------

        if existing_profile:

            db.execute('''
                UPDATE farmer_profile
                SET
                    state = ?,
                    district = ?,
                    village = ?,
                    land_size = ?,
                    land_unit = ?,
                    income_range = ?,
                    farming_experience = ?,
                    currently_growing = ?
                WHERE user_id = ?
            ''', (
                state,
                district,
                village,
                land_size,
                land_unit,
                income_range,
                experience,
                crops,
                session['user_id']
            ))

        # --------------------------------
        # CREATE profile for first time
        # --------------------------------

        else:

            db.execute('''
                INSERT INTO farmer_profile
                (
                    user_id,
                    state,
                    district,
                    village,
                    land_size,
                    land_unit,
                    income_range,
                    farming_experience,
                    currently_growing
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session['user_id'],
                state,
                district,
                village,
                land_size,
                land_unit,
                income_range,
                experience,
                crops
            ))

        db.commit()

        return redirect(url_for('dashboard'))


    # GET request
    # Send existing profile to profile_setup.html
    return render_template(
        'profile_setup.html',
        profile=existing_profile
    )
    
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    profile = db.execute(
        "SELECT * FROM farmer_profile WHERE user_id=?",
        (session['user_id'],)
    ).fetchone()

    income_labels = {
        "below_1L": "Below ₹1L",
        "1L_3L": "₹1L–3L",
        "3L_5L": "₹3L–5L",
        "5L_10L": "₹5L–10L",
        "above_10L": "Above ₹10L"
    }

    user = {
        "name": session.get("full_name", "Farmer"),
        "state": profile["state"] if profile else None,
        "district": profile["district"] if profile else None,
        "village": profile["village"] if profile else None,
        "land_size": profile["land_size"] if profile else None,
        "land_unit": profile["land_unit"] if profile else "acres",
        "income": income_labels.get(profile["income_range"], "Not added") if profile and profile["income_range"] else "Not added",
        "experience": profile["farming_experience"] if profile and profile["farming_experience"] else "Not added",
        "primary_crop": profile["currently_growing"].split(",")[0] if profile and profile["currently_growing"] else "Not added"
    }

    return render_template(
        "dashboard.html",
        user=user,
        tip=random.choice(TIPS),
        full_name=session.get("full_name", "Farmer")
    )
    
    
@app.route('/profile')
@login_required
def profile():
    db = get_db()
    profile_row = db.execute(
        "SELECT * FROM farmer_profile WHERE user_id=?", (session['user_id'],)
    ).fetchone()
    return render_template('profile.html', full_name=session.get('full_name'), profile=profile_row)


# ---------------------------------------------------------
# Schemes module
# ---------------------------------------------------------

def income_range_to_lakh(income_range):
    mapping = {
        "below_1L": 0.5, "1L_3L": 2, "3L_5L": 4, "5L_10L": 7, "above_10L": 12
    }
    return mapping.get(income_range, 2)


@app.route('/schemes')
@login_required
def schemes():
    db = get_db()
    profile_row = db.execute(
        "SELECT * FROM farmer_profile WHERE user_id=?", (session['user_id'],)
    ).fetchone()
    income_lakh = income_range_to_lakh(profile_row['income_range']) if profile_row else 2

    all_schemes = db.execute("SELECT * FROM schemes").fetchall()
    eligible, not_eligible = [], []
    for s in all_schemes:
        if s['min_income_lakh'] <= income_lakh <= s['max_income_lakh']:
            eligible.append(s)
        else:
            not_eligible.append(s)

    saved_ids = {row['scheme_id'] for row in db.execute(
        "SELECT scheme_id FROM saved_schemes WHERE user_id=?", (session['user_id'],)
    ).fetchall()}

    categories = {}
    for s in eligible:
        categories.setdefault(s['category'], []).append(s)

    return render_template('schemes.html', categories=categories, not_eligible=not_eligible, saved_ids=saved_ids)


@app.route('/scheme/<int:scheme_id>')
@login_required
def scheme_detail(scheme_id):
    db = get_db()
    scheme = db.execute("SELECT * FROM schemes WHERE id=?", (scheme_id,)).fetchone()
    is_saved = db.execute(
        "SELECT id FROM saved_schemes WHERE user_id=? AND scheme_id=?",
        (session['user_id'], scheme_id)
    ).fetchone() is not None
    return render_template('scheme_detail.html', scheme=scheme, is_saved=is_saved)


@app.route('/scheme/<int:scheme_id>/save', methods=['POST'])
@login_required
def save_scheme(scheme_id):
    db = get_db()
    existing = db.execute(
        "SELECT id FROM saved_schemes WHERE user_id=? AND scheme_id=?",
        (session['user_id'], scheme_id)
    ).fetchone()
    if existing:
        db.execute("DELETE FROM saved_schemes WHERE id=?", (existing['id'],))
        saved = False
    else:
        db.execute("INSERT INTO saved_schemes (user_id, scheme_id) VALUES (?,?)",
                   (session['user_id'], scheme_id))
        saved = True
    db.commit()
    return jsonify({"saved": saved})


# ---------------------------------------------------------
# Crop advisory module
# ---------------------------------------------------------

@app.route('/crop-advisory', methods=['GET'])
@login_required
def crop_advisory():
    db = get_db()
    last = db.execute(
        "SELECT crop_name, recommended_at FROM crop_recommendations WHERE user_id=? ORDER BY recommended_at DESC LIMIT 1",
        (session['user_id'],)
    ).fetchone()
    return render_template('crop_advisory.html', last_recommendation=last)


@app.route('/crop-advisory/results', methods=['POST'])
@login_required
def crop_advisory_results():
    soil = request.form.get('soil_type')
    water = request.form.get('water')
    season = request.form.get('season')

    db = get_db()

    matches = db.execute(
        """
        SELECT * FROM crops
        WHERE season=?
        ORDER BY (soil_type=?) DESC, (water_need=?) DESC
        """,
        (season, soil, water)
    ).fetchall()

    if matches:
        db.execute(
            "INSERT INTO crop_recommendations (user_id, crop_name) VALUES (?, ?)",
            (session['user_id'], matches[0]['name'])
        )
        db.commit()

    session['crop_result_ids'] = [crop['id'] for crop in matches]

    return redirect(url_for('crop_result'))

@app.route('/crop-result')
@login_required
def crop_result():
    result_ids = session.get('crop_result_ids', [])

    if not result_ids:
        return redirect(url_for('crop_advisory'))

    db = get_db()

    crops = []

    for crop_id in result_ids:
        crop = db.execute(
            "SELECT * FROM crops WHERE id=?",
            (crop_id,)
        ).fetchone()

        if crop:
            crops.append(crop)

    return render_template('crop_result.html', crops=crops)


CROP_IMAGES = {
    "Rice": "rice.jpg",
    "Wheat": "wheat.jpg",
    "Mustard": "mustard.jpg",
    "Soybean": "soybean.jpg",
    "Maize": "Maize.jpg",
    "Cotton": "Cotton.jpg",
    "Sugarcane": "Sugarcane.jpg",
    "Onion": "Onion.jpg",
    "Bajra": "Bajra.jpg",
    "Chana": "Chana.jpg",
    "Groundnut": "Groundnut.jpg",
    "Jowar": "Jowar.jpg",
    "Moong": "Moong.jpg",
    "Potato": "Potato.jpg",
    "Sunflower": "Sunflower.jpg",
    "Tomato": "Tomato.jpg",
    "Tur": "Tur.jpg",
    "Watermelon": "Watermelon.jpg"
}

@app.route('/crop/<int:crop_id>')
@login_required
def crop_detail(crop_id):
    db = get_db()

    crop = db.execute(
        "SELECT * FROM crops WHERE id=?",
        (crop_id,)
    ).fetchone()

    image_filename = CROP_IMAGES.get(crop['name'], "rice.jpg")

    return render_template(
        'crop_detail.html',
        crop=crop,
        image_filename=image_filename
    )

# ---------------------------------------------------------
# Sathi chatbot module (rule-based stub — swap in LLM API call later)
# ---------------------------------------------------------

def screen_for_distress(message):
    lowered = message.lower()
    return any(keyword in lowered for keyword in DISTRESS_KEYWORDS)


def sathi_reply(message, flagged):
    if flagged:
        return (
            "It sounds like you're carrying something really heavy right now. "
            "Please speak with someone you trust. You can also contact "
            "KIRAN at 1800-599-0019 or Tele-MANAS at 14416."
        )

    try:
        response = client.chat.completions.create(
            model="gemini-3.5-flash",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Sathi, a friendly AI farming companion for Indian farmers. "
                        "Reply in the same language style the farmer used — if they write in English, reply in simple English; if they write in Hindi or Hinglish (Roman script), reply in simple Hinglish the same way. "
                        "Keep every answer very short: maximum 2 sentences and 35 words. "
                        "Do not give long introductions, markdown, headings, or bullet points. "
                        "Give only practical help about crops, soil, irrigation, pests, "
                        "weather preparation, and government schemes."
                    )
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        return response.choices[0].message.content

    except Exception as error:
        print("Sathi AI error:", error)
        return "Sathi is unavailable right now. Please try again in a moment."
    
    

@app.route('/sathi')
@login_required
def sathi():
    db = get_db()
    history = db.execute(
        "SELECT * FROM chat_messages WHERE user_id=? ORDER BY created_at ASC",
        (session['user_id'],)
    ).fetchall()
    return render_template('sathi.html', history=history, helplines=HELPLINES)


@app.route('/sathi/send', methods=['POST'])
@login_required
def sathi_send():
    message = request.form.get('message', '').strip()
    if not message:
        return jsonify({"error": "empty"}), 400

    db = get_db()
    flagged = screen_for_distress(message)

    db.execute(
    "INSERT INTO chat_messages (user_id, sender, message, flagged) VALUES (?,?,?,?)",
    (session['user_id'], 'user', message, int(flagged))
    )
    
    db.commit()
    reply = sathi_reply(message, flagged)
    
    db.execute("INSERT INTO chat_messages (user_id, sender, message, flagged) VALUES (?,?,?,?)",
               (session['user_id'], 'sathi', reply, 0))
    db.commit()

    return jsonify({
        "reply": reply,
        "flagged": flagged,
        "helplines": HELPLINES if flagged else None
    })


# ---------------------------------------------------------
# PWA offline route
# ---------------------------------------------------------

@app.route('/offline')
def offline():
    """Offline fallback page served by the service worker."""
    return render_template('offline.html')


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
