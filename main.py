"""
================================================================================
SENSEX OPTIONS AUTO-TRADING ALGO BOT — v2 (సెక్యూరిటీ & మల్టీ-యూజర్ ఫిక్స్‌లతో)
================================================================================
STRATEGY:
  1. 9:15 AM (15-min) SENSEX INDEX candle -> High = CE ATM strike, Low = PE ATM strike
  2. Entry reference = వెనకటి రోజు 10:30 AM candle High -> దొరకకపోతే running day 10:30 High
  3. Entry trigger = reference High + 3 points (breakout SL-BUY order)
  4. Entry అయిన వెంటనే SL = Entry - 15 points
  5. Trailing: ప్రతి 30 points పైకి వెళ్ళితే, SL 15 points పైకి జరుగుతుంది
  6. Target = Entry + 100 points. Target హిట్ అయితే -> రెండు legs స్క్వేర్-ఆఫ్, స్ట్రాటజీ స్టాప్
  7. 3:10 PM కి అన్ని open positions/pending orders ఆటోమేటిక్‌గా square-off/cancel

v2 లో ఏం మారింది (ఇంతకుముందు గుర్తించిన 5 సమస్యలకు ఫిక్స్):
  1. ✅ Admin password ఇప్పుడు ఇక్కడే (server env var) ఉంటుంది, ఎప్పుడూ frontend కి పంపబడదు.
     /admin-login POST తో సరిచూసి, ఒక session token ఇస్తుంది; admin routes ఆ token అడుగుతాయి.
  2. ✅ Broker credentials ఇప్పుడు per-phone (per-user) dict లో ఉంటాయి — ఒక యూజర్ వేరొక
     యూజర్ credentials ని overwrite చేయలేరు. ప్రతి /start-strategy, /stop-strategy,
     /get-history కాల్‌లో "phone" పంపాలి.
  3. ✅ Live market data (9:15 candle, 10:30 candle) దొరకకపోతే — ఇక "fallback price" తో
     బ్లైండ్‌గా ట్రేడ్ చేయదు. బదులుగా ఎర్రర్ రిటర్న్ చేసి స్ట్రాటజీ మొదలవ్వదు.
  4. ✅ pending_requests (అప్రూవల్స్) ఇప్పుడు SQLite (sensex_edge.db) లో పర్సిస్ట్ అవుతాయి —
     సర్వర్ రీస్టార్ట్ అయినా అప్రూవల్/expiry డేటా పోదు (అయితే Render free-tier redeploy
     అయినప్పుడు disk wipe అయ్యే అవకాశం ఇప్పటికీ ఉంది — ఇది platform పరిమితి).
  5. ✅ AngelOne (symboltoken) మరియు Dhan (securityId) కోసం ఇప్పుడు వాళ్ళ అధికారిక
     scrip-master ఫైళ్ళ నుండి నిజంగా లుకప్ చేసే కోడ్ ఉంది (కేవలం placeholder కాదు).
     ⚠️ ఈ ఫైళ్ళ column names broker వైపు మారే అవకాశం ఉంది — వాడే ముందు ఒకసారి
     డౌన్‌లోడ్ చేసి, ఇక్కడి field mapping సరిపోతుందో verify చేసుకోండి.

⚠️ ఇప్పటికీ కోడ్ ద్వారా solve కానివి (దయచేసి గమనించండి):
  - SEBI ఏప్రిల్ 2026 రిటైల్ ఆల్గో ట్రేడింగ్ ఫ్రేమ్‌వర్క్ (Algo-ID, broker-registration) —
    ఇది ఒక legal/compliance ప్రాసెస్, ఇది కోడ్‌లో ఇంప్లిమెంట్ చేయలేం. మీ బ్రోకర్ ద్వారా
    అధికారికంగా రిజిస్టర్ చేసుకోవాలి, లేకపోతే ఆర్డర్లు రిజెక్ట్ అయ్యే/ఖాతా flag అయ్యే ప్రమాదం ఉంది.
  - Render లాంటి free-tier hosting లో redeploy అయినప్పుడు SQLite ఫైల్ కూడా పోయే అవకాశం
    ఉంది — పూర్తి persistence కోసం paid persistent disk లేదా external DB (Postgres) వాడాలి.
  - మిడ్-ట్రేడ్ సర్వర్ క్రాష్ అయితే, బ్రోకర్ వైపు ఓపెన్ పొజిషన్ ఉండొచ్చు కానీ ఇక్కడి
    ట్రైలింగ్-SL మానిటరింగ్ లూప్ ఆగిపోతుంది — దీనికి బ్రోకర్ position-reconciliation
    logic (సర్వర్ startup లో ప్రతి బ్రోకర్ APIకి "get positions" కాల్ చేసి state రీబిల్డ్
    చేయడం) అవసరం, ఇది ఇంకా add చేయలేదు.
================================================================================
"""

import os
import re
import csv
import io
import json
import gzip
import math
import time
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==============================================================================
# 1. STRATEGY CONSTANTS
# ==============================================================================

FULL_TARGET_POINTS = 100        # ఏకైక ₹2,499 ప్లాన్ — target (2026-10-08: single-price simplification)
TRAIL_STEP_POINTS = 30
TRAIL_SL_MOVE_POINTS = 15
INITIAL_SL_POINTS = 15          # ⚠️ పాత strategy లో వాడింది — కొత్త entry లాజిక్ ఇక దీన్ని వాడదు
                                 # (REVERSAL_SL_POINTS వాడుతుంది), కానీ history/reference కోసం ఉంచాం.
ENTRY_BUFFER_POINTS = 3          # ⚠️ పాత "High+3 breakout" entry లాజిక్‌కి వాడింది — ఇప్పుడు వాడదు.
# ⚠️ కొత్త ఎంట్రీ లాజిక్ (యూజర్ కోరిక ప్రకారం, 2026-10-07): 10:30 candle పూర్తయ్యాక, CE/PE
# ఆప్షన్ల సొంత 10:30 LOW కన్నా BREAKOUT_BREAK_POINTS (5) పాయింట్లు కిందికి ఏదో ఒక ఆప్షన్
# బ్రేక్ అయితే, ఆ ఆప్షన్‌లో కాదు — దాని OPPOSITE ఆప్షన్‌లో ఎంట్రీ తీసుకుంటాం (ఉదా: CE తన
# low బ్రేక్ చేస్తే PE లో ఎంట్రీ). ఈ ఎంట్రీకి initial SL REVERSAL_SL_POINTS (10) పాయింట్లు
# (పాత 15 కాదు). Entry తర్వాత Trailing SL (30↑→15↑) మరియు Target (100/50, ప్లాన్ బట్టి)
# పాత స్ట్రాటజీ లాగే వర్తిస్తాయి — ఇవి మారలేదు. SL hit అయితే (reversal), మళ్ళీ అదే బ్రేక్‌అవుట్
# కండిషన్ (ధర ముందు level పైకి recover అయ్యి, మళ్ళీ కిందికి బ్రేక్ అయితేనే) తిరిగి వస్తే
# re-entry తీసుకుంటాం — ఇలా రోజుకి మొత్తం MAX_ENTRY_ATTEMPTS (3) సార్లు మాత్రమే.
BREAKOUT_BREAK_POINTS = 5
REVERSAL_SL_POINTS = 10
MAX_ENTRY_ATTEMPTS = 3
MONITOR_POLL_SECONDS = 2
SQUARE_OFF_TIME = "15:10"
SUBSCRIPTION_DAYS = 30
# ⚠️ మార్పు (యూజర్ కోరిక ప్రకారం): ఇంతకుముందు 9:15 candle కోసం 09:45 వరకే, 10:30
# entry reference కోసం 11:00 వరకే wait చేసి "Abort" అయ్యేది. యూజర్ ఎప్పుడు Start
# నొక్కినా (ఉదా. 10:30కే) — డేటా దొరికిన వెంటనే entry ప్రయత్నించాలి, దొరక్కపోయినా
# రోజంతా (మార్కెట్ ముగిసేదాకా) "running/monitoring" స్థితిలోనే ఉండాలి, మధ్యలో
# ఆగిపోకూడదు. కాబట్టి ఇప్పుడు రెండు cutoff‌లూ SQUARE_OFF_TIME కి extend చేసాం.
DATA_WAIT_CUTOFF_TIME = SQUARE_OFF_TIME       # 9:15 candle కోసం మార్కెట్ ముగిసేదాకా wait
ENTRY_REF_WAIT_CUTOFF_TIME = SQUARE_OFF_TIME  # ఈరోజు 10:30 candle (entry reference) కోసం మార్కెట్ ముగిసేదాకా wait
DATA_WAIT_POLL_SECONDS = 5        # ఎంత తరచుగా 9:15 candle దొరికిందా అని రీ-చెక్ చేయాలి

SENSEX_INDEX_KEY_UPSTOX = "BSE_INDEX|SENSEX"

# ⚠️ దయచేసి ఇది env var గా Render లో సెట్ చేయండి (Settings → Environment).
# సెట్ చేయకపోతే fallback డిఫాల్ట్ వాడుతుంది — production లో ఇది సురక్షితం కాదు.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "merababa@123")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensex_edge.db")

# ==============================================================================
# ⭐ CRITICAL FIX: IST TIMEZONE HELPERS
# ==============================================================================
# Render (మరియు చాలా cloud hosts) సర్వర్ system clock ఎప్పుడూ UTC లో ఉంటుంది,
# IST (India) లో కాదు. మన కోడ్‌లో SQUARE_OFF_TIME="15:10", DATA_WAIT_CUTOFF_TIME="09:45"
# లాంటి cutoff strings అన్నీ IST ఉద్దేశించి రాశాం — కానీ ఇంతకుముందు వీటిని
# datetime.now() (server యొక్క UTC టైమ్) తోనే compare చేస్తున్నాం, ఇది తప్పు!
# ఉదా: UTC 09:45 అంటే వాస్తవానికి IST 3:15 PM — పూర్తిగా వేరే సమయం.
# ఇదే కారణంగా స్ట్రాటజీ తప్పు సమయాల్లో abort అవుతూ, తప్పు సమయాల్లో wait
# చేస్తూ ఉండేది. ఇప్పుడు, TIME-OF-DAY comparisons అన్నీ ఈ IST-aware
# now_ist()/today_ist_str() ఫంక్షన్ల ద్వారానే జరగాలి — plain datetime.now() ద్వారా కాదు.
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    """ప్రస్తుత సమయం, IST timezone-aware గా (server ఎక్కడ run అయినా సరే సరైన IST టైమ్ ఇస్తుంది)."""
    return datetime.now(timezone.utc).astimezone(IST)


def today_ist_str():
    """ఈరోజు తేదీ (YYYY-MM-DD), IST క్యాలెండర్ ప్రకారం."""
    return now_ist().strftime("%Y-%m-%d")


def _days_since_ist(dt):
    """
    approved_at వంటి గతంలో సేవ్ అయిన timestamp నుండి ఇప్పటివరకు ఎన్ని రోజులు
    గడిచాయో లెక్కిస్తుంది. ఈ fix కి ముందు సేవ్ అయిన timestamps (naive, UTC అని
    అనుకోవాలి) మరియు fix తర్వాత సేవ్ అయినవి (IST-aware) రెండింటికీ సురక్షితంగా పనిచేస్తుంది.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now_ist() - dt.astimezone(IST)).days



# ==============================================================================
# 2. PERSISTENT STORAGE (SQLite) — అప్రూవల్స్ ఇక్కడ ఉంటాయి, restart అయినా పోవు
# ==============================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            approved_at TEXT,
            plan TEXT DEFAULT 'FULL'
        )
    """)
    # ఇప్పటికే ఉన్న పాత DB ఫైల్‌కి 'plan' కాలమ్ లేకపోతే add చేయడం (migration-safe;
    # ఇప్పటికే ఉంటే exception వస్తుంది, దాన్ని ఇగ్నర్ చేస్తాం)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'FULL'")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


init_db()


def db_get_user(phone):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return dict(row) if row else None


def db_upsert_user(phone, status, approved_at=None, plan=None):
    """
    plan=None అయితే (ఉదా. admin approve/reject చేసేటప్పుడు), ఇప్పటికే ఉన్న plan value ని
    అలానే ఉంచుతుంది. (2026-10-08 నుండి ఒకే ₹2,499/FULL ప్లాన్ మాత్రమే ఉంది.)
    """
    conn = get_db()
    existing = conn.execute("SELECT plan FROM users WHERE phone = ?", (phone,)).fetchone()
    final_plan = plan if plan is not None else (existing["plan"] if existing and existing["plan"] else "FULL")
    conn.execute("""
        INSERT INTO users (phone, status, approved_at, plan) VALUES (?, ?, ?, ?)
        ON CONFLICT(phone) DO UPDATE SET status = excluded.status, approved_at = excluded.approved_at, plan = excluded.plan
    """, (phone, status, approved_at, final_plan))
    conn.commit()
    conn.close()


def db_list_pending():
    conn = get_db()
    rows = conn.execute("SELECT phone, plan FROM users WHERE status = 'PENDING'").fetchall()
    conn.close()
    return [{"phone": r["phone"], "plan": r["plan"] or "FULL"} for r in rows]

# ==============================================================================
# 3. ADMIN AUTH — password ఇక్కడే ఉంటుంది, frontend కి ఎప్పుడూ పంపబడదు
# ==============================================================================

admin_sessions = set()  # valid session tokens (in-memory; restart అయితే admin మళ్ళీ login కావాలి)


def is_admin_request():
    token = request.headers.get("X-Admin-Token", "")
    return token in admin_sessions


@app.route('/', methods=['GET'])
@app.route('/ping', methods=['GET'])
def ping():
    """
    UptimeRobot (లేదా ఏ keep-alive pinger అయినా) ఇక్కడికి ping చేయొచ్చు — ఇది Render
    free-tier సర్వీస్‌ని awake గా ఉంచడానికి సహాయపడుతుంది (ఖచ్చితమైన ఫిక్స్ కాదు, ఇది
    పైన ఇచ్చిన Render paid-plan upgrade కి ఒక ఉచిత workaround మాత్రమే).
    """
    return jsonify({"status": "ok", "service": "sensex-edge-telugu-backend"}), 200


@app.route('/admin-login', methods=['POST', 'OPTIONS'])
def admin_login():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    data = request.json or {}
    password = data.get("password", "")
    if password == ADMIN_PASSWORD:
        token = secrets.token_hex(24)
        admin_sessions.add(token)
        return jsonify({"status": "success", "token": token}), 200
    return jsonify({"status": "error", "message": "Wrong password"}), 401

# ==============================================================================
# 4. PER-USER STATE (multi-user safe) — global కాకుండా phone-keyed dicts
# ==============================================================================

user_sessions = {}      # phone -> {"broker":.., "access_token":.., "api_key":.., "lots":.., "lot_size":..}
trading_states = {}     # phone -> {"is_active":.., "sl_hit_count":.., "trade_history":.., "legs": {...}}
active_threads = {}     # phone -> Thread
state_lock = threading.Lock()


def new_trading_state():
    return {
        "is_active": False,
        "phase": "WAITING_FOR_915_DATA",   # WAITING_FOR_915_DATA -> TRADING -> STOPPED
        "sl_hit_count": 0,
        "trade_history": [],
        "legs": {"CE": {}, "PE": {}},
        "spot_915_high": None,
        "spot_915_low": None,
        "attempts_used": 0,        # ⚠️ కొత్త: ఈరోజు ఎన్ని ఎంట్రీ ప్రయత్నాలు జరిగాయో (max MAX_ENTRY_ATTEMPTS)
    }

# ==============================================================================
# 5. EXPIRY & INSTRUMENT RESOLUTION
# ==============================================================================

def get_next_expiry_date():
    today = now_ist()
    days_ahead = (3 - today.weekday()) % 7  # 3 = Thursday
    if days_ahead == 0 and today.hour >= 15:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


_sensex_index_key_cache = {"key": None, "fetched_at": None}


def resolve_upstox_sensex_index_key(access_token):
    """
    ⚠️ ఇంతకుముందు SENSEX_INDEX_KEY_UPSTOX హార్డ్‌కోడ్ ("BSE_INDEX|SENSEX") వాడేవాళ్ళం —
    ఇది broker వైపు మారిపోయి ఉండొచ్చు అనేది 9:15 candle పదేపదే fail అవడానికి ఒక అనుమానిత
    కారణం. ఇప్పుడు ముందు search API ద్వారా నిజమైన instrument_key కనిపెట్టే ప్రయత్నం చేస్తాం,
    దొరకకపోతేనే హార్డ్‌కోడెడ్ విలువకి fallback అవుతాం. 24 గంటలకోసారి cache అవుతుంది.
    """
    now = datetime.now()
    if (_sensex_index_key_cache["key"] and _sensex_index_key_cache["fetched_at"]
            and (now - _sensex_index_key_cache["fetched_at"]).total_seconds() < 86400):
        return _sensex_index_key_cache["key"]

    try:
        url = "https://api.upstox.com/v2/instruments/search?query=SENSEX"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
        res = requests.get(url, headers=headers, timeout=10).json()
        for item in res.get("data", []):
            seg = str(item.get("segment") or item.get("exchange") or "").upper()
            itype = str(item.get("instrument_type") or "").upper()
            name = str(item.get("trading_symbol") or item.get("name") or "").upper()
            if "INDEX" in seg or "INDEX" in itype or name == "SENSEX":
                key = item.get("instrument_key")
                if key:
                    print(f"[UPSTOX] SENSEX index key search ద్వారా దొరికింది: {key}")
                    _sensex_index_key_cache["key"] = key
                    _sensex_index_key_cache["fetched_at"] = now
                    return key
    except Exception as e:
        print(f"[UPSTOX] SENSEX index key search fail అయ్యింది: {e} — hardcoded fallback వాడుతున్నాం.")

    return SENSEX_INDEX_KEY_UPSTOX


# --- Upstox: SENSEX options — అధికారిక instrument-master dump (strike/type/expiry లుకప్) ---
_upstox_sensex_options_cache = {"data": None, "fetched_at": None}

# ⚠️ ఫిక్స్ (రూట్-కాజ్): /v2/instruments/search?query=SENSEX అనేది ఒక fuzzy TEXT
# సెర్చ్ మాత్రమే — ఇది పూర్తి option chain (ప్రతి strike) రిటర్న్ చేయదు, కేవలం కొన్ని
# "best match" results మాత్రమే ఇస్తుంది. అందుకే 9:15 strikes సరిగ్గా వచ్చినా (అది index
# search మీదే ఆధారపడింది), 10:30 నాటికి ఒక నిర్దిష్ట CE/PE strike (ఉదా. 72400CE) ఆ
# limited results లో లేకపోవడం వల్ల instrument key resolve ఎప్పటికీ దొరకకుండా retry లూప్‌లో
# ఉండిపోయింది. దీనికి బదులు Upstox అధికారికంగా పబ్లిష్ చేసే పూర్తి instrument-master file
# (ప్రతి BSE instrument — index, options, అన్నీ) డౌన్‌లోడ్ చేసి, ఇక్కడే local గా
# name=SENSEX + instrument_type(CE/PE) + strike_price ఆధారంగా ఖచ్చితంగా ఫిల్టర్ చేస్తాం.
_UPSTOX_BSE_MASTER_URLS = [
    "https://assets.upstox.com/market-quote/instruments/exchange/BSE.json.gz",
    "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz",
]


def _load_upstox_sensex_options(access_token=None):
    now = datetime.now()
    if (_upstox_sensex_options_cache["data"] is not None and _upstox_sensex_options_cache["fetched_at"]
            and (now - _upstox_sensex_options_cache["fetched_at"]).total_seconds() < 3600):
        return _upstox_sensex_options_cache["data"]

    for url in _UPSTOX_BSE_MASTER_URLS:
        try:
            res = requests.get(url, timeout=45)
            res.raise_for_status()
            raw_bytes = res.content
            try:
                raw_bytes = gzip.decompress(raw_bytes)
            except OSError:
                pass  # already decompressed by requests/server
            all_items = json.loads(raw_bytes)
            items = []
            for it in all_items:
                name = str(it.get("name") or it.get("underlying_symbol") or it.get("asset_symbol") or "").upper()
                itype = str(it.get("instrument_type") or it.get("option_type") or "").upper()
                if name == "SENSEX" and itype in ("CE", "PE"):
                    items.append(it)
            if items:
                _upstox_sensex_options_cache["data"] = items
                _upstox_sensex_options_cache["fetched_at"] = now
                print(f"[UPSTOX] Instrument master ({url}) నుండి SENSEX options: {len(items)} లోడ్ అయ్యాయి")
                return items
            print(f"[UPSTOX] {url} లో SENSEX CE/PE items దొరకలేదు, next URL ట్రై చేస్తోంది...")
        except Exception as e:
            print(f"[UPSTOX] Instrument master load FAIL ({url}): {e}")
            continue

    print("[UPSTOX] ⚠️ అన్ని instrument-master URLs fail అయ్యాయి — cached (ఉంటే) లేదా ఖాలీ లిస్ట్ వాడుతున్నాం.")
    return _upstox_sensex_options_cache["data"] or []


def get_upstox_instrument_key(trading_symbol, access_token):
    """
    CE/PE symbol ("SENSEX26OCT73700CE") ని regex తో parse చేసి strike+type
    తీసుకుని, cached broad-search list లో నుండి సరైన instrument_key వెతుకుతుంది.
    Match దొరకకపోతే None రిటర్న్ చేస్తుంది (ఇంతకుముందు తప్పుగా raw string
    రిటర్న్ చేసేది — అదే ఇన్‌వాలిడ్ ఫార్మాట్ ఎర్రర్‌కి ఒక కారణం).
    """
    m = re.match(r"^(?:BSE:)?SENSEX\d{2}[A-Z]{3}(\d+)(CE|PE)$", trading_symbol)
    if m:
        strike = float(m.group(1))
        option_type = m.group(2)
        items = _load_upstox_sensex_options(access_token)
        candidates = []
        for item in items:
            itype = str(item.get("instrument_type") or item.get("option_type") or "").upper()
            strike_val = item.get("strike_price")
            if itype != option_type or strike_val is None:
                continue
            try:
                if abs(float(strike_val) - strike) < 0.01:
                    candidates.append(item)
            except (TypeError, ValueError):
                continue
        if candidates:
            def _expiry_sort_key(it):
                exp = it.get("expiry")
                try:
                    return float(exp)  # epoch millis (instrument-master format)
                except (TypeError, ValueError):
                    return str(exp or "")  # date string fallback
            candidates.sort(key=_expiry_sort_key)
            chosen = candidates[0]
            key = chosen.get("instrument_key")
            print(f"[UPSTOX] {trading_symbol} -> {key} (strike:{strike} type:{option_type})")
            return key
        print(f"[UPSTOX] ⚠️ {trading_symbol}: strike {strike} {option_type} కి ఏ instrument_key match దొరకలేదు "
              f"(cached items: {len(items)}). Expiry తేదీ/strike step తప్పు అయి ఉండొచ్చు.")
        return None

    # Regex match కాని symbols (ఉదా: index) కోసం direct-search fallback
    try:
        url = f"https://api.upstox.com/v2/instruments/search?query={trading_symbol}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
        res = requests.get(url, headers=headers, timeout=10).json()
        data = res.get("data", [])
        if data:
            for item in data:
                if item.get("trading_symbol") == trading_symbol or item.get("short_name") == trading_symbol:
                    return item.get("instrument_key")
            return data[0].get("instrument_key")
    except Exception as e:
        print(f"[UPSTOX SEARCH ERROR] {e}")
    return None


# --- AngelOne: నిజమైన scrip-master లుకప్ (కేవలం placeholder కాదు) ---
_angelone_cache = {"lookup": None, "fetched_at": None}
_ANGELONE_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"


def _load_angelone_scrip_master():
    now = datetime.now()
    if (_angelone_cache["lookup"] is not None and _angelone_cache["fetched_at"]
            and (now - _angelone_cache["fetched_at"]).total_seconds() < 86400):
        return _angelone_cache["lookup"]
    try:
        res = requests.get(_ANGELONE_MASTER_URL, timeout=30)
        items = res.json()
        # ⚠️ ఈ field names (symbol/token) AngelOne ఫైల్ ప్రస్తుత structure ఆధారంగా —
        # వాడే ముందు ఒకసారి ఈ JSON ని డౌన్‌లోడ్ చేసి ఖచ్చితత్వం verify చేసుకోండి.
        lookup = {}
        for item in items:
            sym = item.get("symbol")
            token = item.get("token")
            if sym and token:
                lookup[sym] = token
        _angelone_cache["lookup"] = lookup
        _angelone_cache["fetched_at"] = now
        print(f"[ANGELONE] Scrip master loaded: {len(lookup)} symbols")
        return lookup
    except Exception as e:
        print(f"[ANGELONE SCRIP MASTER ERROR] {e}")
        return _angelone_cache["lookup"] or {}


def resolve_angelone_symboltoken(symbol):
    lookup = _load_angelone_scrip_master()
    token = lookup.get(symbol)
    if not token:
        print(f"[ANGELONE] ⚠️ symboltoken దొరకలేదు: {symbol}")
    return token


# --- Dhan: నిజమైన scrip-master లుకప్ (కేవలం placeholder కాదు) ---
_dhan_cache = {"lookup": None, "fetched_at": None}
_DHAN_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"


def _load_dhan_scrip_master():
    now = datetime.now()
    if (_dhan_cache["lookup"] is not None and _dhan_cache["fetched_at"]
            and (now - _dhan_cache["fetched_at"]).total_seconds() < 86400):
        return _dhan_cache["lookup"]
    try:
        res = requests.get(_DHAN_MASTER_URL, timeout=30)
        # ⚠️ ఈ column names (SEM_TRADING_SYMBOL / SEM_SMST_SECURITY_ID) Dhan CSV ప్రస్తుత
        # structure ఆధారంగా — వాడే ముందు ఒకసారి ఈ CSV డౌన్‌లోడ్ చేసి headers verify చేసుకోండి.
        reader = csv.DictReader(io.StringIO(res.text))
        lookup = {}
        for row in reader:
            sym = row.get("SEM_TRADING_SYMBOL")
            sec_id = row.get("SEM_SMST_SECURITY_ID")
            if sym and sec_id:
                lookup[sym] = sec_id
        _dhan_cache["lookup"] = lookup
        _dhan_cache["fetched_at"] = now
        print(f"[DHAN] Scrip master loaded: {len(lookup)} symbols")
        return lookup
    except Exception as e:
        print(f"[DHAN SCRIP MASTER ERROR] {e}")
        return _dhan_cache["lookup"] or {}


def resolve_dhan_security_id(symbol):
    lookup = _load_dhan_scrip_master()
    sec_id = lookup.get(symbol)
    if not sec_id:
        print(f"[DHAN] ⚠️ securityId దొరకలేదు: {symbol}")
    return sec_id


# --- Zerodha: నిజమైన instrument-dump లుకప్ (కేవలం placeholder కాదు) ---
_zerodha_cache = {"lookup": None, "fetched_at": None}
_ZERODHA_INSTRUMENTS_URL = "https://api.kite.trade/instruments"


def _load_zerodha_instruments(access_token, api_key):
    now = datetime.now()
    if (_zerodha_cache["lookup"] is not None and _zerodha_cache["fetched_at"]
            and (now - _zerodha_cache["fetched_at"]).total_seconds() < 86400):
        return _zerodha_cache["lookup"]
    try:
        headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
        res = requests.get(_ZERODHA_INSTRUMENTS_URL, headers=headers, timeout=30)
        # ⚠️ ఈ column names (tradingsymbol/instrument_token) Zerodha CSV ప్రస్తుత
        # structure ఆధారంగా — వాడే ముందు ఒకసారి verify చేసుకోండి.
        reader = csv.DictReader(io.StringIO(res.text))
        lookup = {}
        for row in reader:
            sym = row.get("tradingsymbol")
            token = row.get("instrument_token")
            if sym and token:
                lookup[sym] = token
        _zerodha_cache["lookup"] = lookup
        _zerodha_cache["fetched_at"] = now
        print(f"[ZERODHA] Instruments loaded: {len(lookup)} symbols")
        return lookup
    except Exception as e:
        print(f"[ZERODHA INSTRUMENTS ERROR] {e}")
        return _zerodha_cache["lookup"] or {}


def resolve_zerodha_instrument_token(symbol, access_token, api_key):
    lookup = _load_zerodha_instruments(access_token, api_key)
    token = lookup.get(symbol)
    if not token:
        print(f"[ZERODHA] ⚠️ instrument_token దొరకలేదు: {symbol}")
    return token

# ==============================================================================
# 6. 9:15 AM CANDLE (INDEX) & 10:30 AM CANDLE — 5 బ్రోకర్లకూ ఉమ్మడి లాజిక్
#
# ⚠️ ముఖ్యమైన గమనిక: Upstox "15minute" interval ఇక support చేయదని (HTTP 400,
# UDAPI1020) direct గా verify చేసాం. దీన్ని బట్టి, అన్ని 5 బ్రోకర్లకూ ఇక్కడ
# ఏకరీతిగా "1-minute" candles తెచ్చి, కావాల్సిన 15-నిమిషాల విండో (09:15-09:29
# లేదా 10:30-10:44) లో High/Low ని మనమే calculate చేస్తాం — ఇది broker-side
# "15minute" ఇంటర్వెల్ deprecate అయినా/మారినా పనిచేసేలా futureproof గా ఉంటుంది.
#
# ⚠️ Zerodha/AngelOne/Dhan/Fyers APIs ఇక్కడ public docs ఆధారంగా best-effort గా
# రాసాను — వీటిని నేను live గా verify చేయలేదు (Upstox మాత్రమే live verify
# చేయగలిగాను). ఏదైనా fail అయితే, exact HTTP status + response Render Logs లో
# కనిపిస్తుంది, దాంతో మనం ఖచ్చితంగా ఫిక్స్ చేయగలం.
# ==============================================================================

def _candle_time_str(candle_ts):
    """Candle timestamp (ఉదా. '2026-08-26T09:15:00+05:30') నుండి 'HH:MM' తీస్తుంది."""
    if "T" in candle_ts:
        return candle_ts.split("T")[1][:5]
    return candle_ts[11:16]


def _resolve_index_instrument(broker, access_token, api_key=""):
    """SENSEX index కోసం, ప్రతి బ్రోకర్‌కి కావాల్సిన identifier ని రిటర్న్ చేస్తుంది."""
    broker = broker.lower()
    if broker == "upstox":
        return resolve_upstox_sensex_index_key(access_token)
    elif broker == "zerodha":
        return resolve_zerodha_instrument_token("SENSEX", access_token, api_key)
    elif broker == "angelone":
        return resolve_angelone_symboltoken("SENSEX")
    elif broker == "dhan":
        return resolve_dhan_security_id("SENSEX")
    elif broker == "fyers":
        # ⚠️ ఇది best-effort గా అంచనా వేసిన symbol format — verify చేయాలి.
        return "BSE:SENSEX-INDEX"
    return None


def _resolve_option_instrument(broker, symbol, access_token, api_key=""):
    """CE/PE ఆప్షన్ సింబల్ కోసం, ప్రతి బ్రోకర్‌కి కావాల్సిన identifier ని రిటర్న్ చేస్తుంది."""
    broker = broker.lower()
    if broker == "upstox":
        return get_upstox_instrument_key(symbol, access_token)
    elif broker == "zerodha":
        return resolve_zerodha_instrument_token(symbol, access_token, api_key)
    elif broker == "angelone":
        return resolve_angelone_symboltoken(symbol)
    elif broker == "dhan":
        return resolve_dhan_security_id(symbol)
    elif broker == "fyers":
        return symbol  # Fyers ఇప్పటికే పూర్తి "BSE:SENSEX26JANxxxxxCE" ఫార్మాట్ symbol వాడుతుంది
    return None


def _fetch_1min_candles(broker, instrument_id, access_token, api_key, date_str):
    """
    5 బ్రోకర్లలో దేనికైనా, ఆ రోజు 1-min candles తెచ్చి, అన్నింటినీ ఒకే
    normalized format కి మారుస్తుంది: [{"time": "HH:MM", "high": float, "low": float}, ...]
    Returns: (candles_list, error_message_or_None)
    ఏదైనా fail అయితే ([], "exact reason") రిటర్న్ చేస్తుంది — ఈ reason ఇప్పుడు
    App లోని Live Trade Alerts లో కూడా నేరుగా కనిపిస్తుంది (Render Logs వెళ్ళక్కర్లేదు).
    """
    broker = broker.lower()
    normalized = []
    if not instrument_id:
        msg = "instrument identifier దొరకలేదు (broker నుండి symbol/token resolve కాలేదు)."
        print(f"[{broker.upper()} CANDLE] ❌ {msg}")
        return [], msg

    try:
        if broker == "upstox":
            # ⚠️ కీలకమైన fix: 'historical-candle' endpoint ముగిసిన (past) రోజుల డేటా కోసమే —
            # ఈరోజు (live/running day) డేటా కోసం ప్రత్యేక 'intraday' endpoint వాడాలి.
            # ఇదివరకు ఎప్పుడూ 'today' తేదీతోనే historical endpoint కొట్టేవాళ్ళం, అందుకే
            # HTTP 200 వచ్చినా candles ఖాళీగా వచ్చేవి. ఇప్పుడు ఈరోజైతే intraday,
            # పాత తేదీ అయితే historical — రెండూ సపోర్ట్ చేస్తాం.
            if date_str == today_ist_str():
                url = f"https://api.upstox.com/v2/historical-candle/intraday/{instrument_id}/1minute"
            else:
                url = f"https://api.upstox.com/v2/historical-candle/{instrument_id}/1minute/{date_str}/{date_str}"
            headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers, timeout=10)
            res = response.json()
            if response.status_code != 200:
                msg = f"HTTP {response.status_code}: {str(res)[:200]}"
                print(f"[UPSTOX CANDLE] ❌ {msg}")
                return [], msg
            for c in res.get("data", {}).get("candles", []):
                normalized.append({"time": _candle_time_str(c[0]), "high": float(c[2]), "low": float(c[3])})

        elif broker == "zerodha":
            url = (f"https://api.kite.trade/instruments/historical/{instrument_id}/minute"
                   f"?from={date_str}&to={date_str}")
            headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
            response = requests.get(url, headers=headers, timeout=10)
            res = response.json()
            if response.status_code != 200:
                msg = f"HTTP {response.status_code}: {str(res)[:200]}"
                print(f"[ZERODHA CANDLE] ❌ {msg}")
                return [], msg
            for c in res.get("data", {}).get("candles", []):
                normalized.append({"time": _candle_time_str(str(c[0])), "high": float(c[2]), "low": float(c[3])})

        elif broker == "angelone":
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/historical/v1/getCandleData"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "Accept": "application/json", "X-PrivateKey": api_key,
                       "X-UserType": "USER", "X-SourceID": "WEB",
                       "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "127.0.0.1",
                       "X-MACAddress": "MAC_ADDRESS"}
            payload = {"exchange": "BSE", "symboltoken": instrument_id, "interval": "ONE_MINUTE",
                       "fromdate": f"{date_str} 09:00", "todate": f"{date_str} 15:30"}
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            res = response.json()
            if response.status_code != 200 or res.get("status") is False:
                msg = f"HTTP {response.status_code}: {str(res)[:200]}"
                print(f"[ANGELONE CANDLE] ❌ {msg}")
                return [], msg
            for c in res.get("data", []):
                normalized.append({"time": _candle_time_str(str(c[0])), "high": float(c[2]), "low": float(c[3])})

        elif broker == "dhan":
            url = "https://api.dhan.co/v2/charts/intraday"
            headers = {"access-token": access_token, "client-id": api_key, "Content-Type": "application/json"}
            payload = {"securityId": instrument_id, "exchangeSegment": "IDX_I", "instrument": "INDEX",
                       "interval": "1", "fromDate": date_str, "toDate": date_str}
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            res = response.json()
            if response.status_code != 200:
                msg = f"HTTP {response.status_code}: {str(res)[:200]}"
                print(f"[DHAN CANDLE] ❌ {msg}")
                return [], msg
            # ⚠️ Dhan parallel-array format (list-of-rows కాదు): {"open":[...],"high":[...],...}
            highs, lows, timestamps = res.get("high", []), res.get("low", []), res.get("timestamp", [])
            for ts, h, l in zip(timestamps, highs, lows):
                dt = datetime.fromtimestamp(ts)
                normalized.append({"time": dt.strftime("%H:%M"), "high": float(h), "low": float(l)})

        elif broker == "fyers":
            url = (f"https://api-v3.fyers.in/data/history?symbol={instrument_id}&resolution=1"
                   f"&date_format=1&range_from={date_str}&range_to={date_str}&cont_flag=1")
            headers = {"Authorization": f"{api_key}:{access_token}"}
            response = requests.get(url, headers=headers, timeout=10)
            res = response.json()
            if response.status_code != 200 or res.get("s") != "ok":
                msg = f"HTTP {response.status_code}: {str(res)[:200]}"
                print(f"[FYERS CANDLE] ❌ {msg}")
                return [], msg
            for c in res.get("candles", []):
                dt = datetime.fromtimestamp(c[0])  # Fyers timestamp epoch (int) గా వస్తుంది
                normalized.append({"time": dt.strftime("%H:%M"), "high": float(c[2]), "low": float(c[3])})

        else:
            msg = f"{broker} కోసం candle API ఇంకా ఇంప్లిమెంట్ కాలేదు."
            print(f"[WARNING] {msg}")
            return [], msg

    except Exception as e:
        msg = f"Exception: {e}"
        print(f"[{broker.upper()} CANDLE] ❌ {msg}")
        return [], msg

    if not normalized:
        return [], "HTTP 200 వచ్చింది కానీ candles ఖాళీగా ఉంది (డేటా ఇంకా లేదు కావొచ్చు)."

    return normalized, None


def fetch_915_high_low(broker, access_token, api_key=""):
    """
    9:15-09:29 విండో లో (5 బ్రోకర్లలో ఏదైనా) 1-min candles అగ్రిగేట్ చేసి High/Low ఇస్తుంది.
    Returns: (high, low, error_message_or_None)
    """
    broker = str(broker).lower()
    today_str = today_ist_str()
    instrument_id = _resolve_index_instrument(broker, access_token, api_key)

    candles, err = _fetch_1min_candles(broker, instrument_id, access_token, api_key, today_str)
    if err:
        print(f"[ERROR] 9:15 candle live data దొరకలేదు — {err}")
        return None, None, err

    window = [c for c in candles if "09:15" <= c["time"] <= "09:29"]
    if not window:
        msg = f"09:15-09:29 window లో candles దొరకలేదు (మొత్తం {len(candles)} candles వచ్చాయి, ఇంకా ఆ సమయం అవ్వలేదేమో)."
        print(f"[{broker.upper()}] ⚠️ {msg}")
        return None, None, msg

    high = max(c["high"] for c in window)
    low = min(c["low"] for c in window)
    print(f"[ALGO] 9:15 Candle ({broker}, {len(window)} bars) -> High:{high} Low:{low}")
    return high, low, None


def calculate_atm_strikes(high_915, low_915, broker):
    ce_atm = round(high_915 / 100) * 100
    pe_atm = round(low_915 / 100) * 100
    broker = str(broker).lower()
    expiry = get_next_expiry_date()
    yy, mmm = expiry.strftime("%y"), expiry.strftime("%b").upper()

    if broker == "zerodha":
        ce_symbol, pe_symbol = f"SENSEX{yy}{mmm}{ce_atm}CE", f"SENSEX{yy}{mmm}{pe_atm}PE"
    elif broker == "fyers":
        ce_symbol, pe_symbol = f"BSE:SENSEX{yy}{mmm}{ce_atm}CE", f"BSE:SENSEX{yy}{mmm}{pe_atm}PE"
    else:
        # ⚠️ ఫిక్స్: ఇంతకుముందు ఇక్కడ expiry (yy+mmm) పూర్తిగా మిస్ అయ్యింది — "SENSEX73700CE"
        # అనేది ఏ నిజమైన instrument కీ match కాదు (Upstox "invalid instrument key format"
        # error ఇచ్చింది). ఇప్పుడు zerodha మాదిరిగానే expiry చేర్చాం.
        ce_symbol, pe_symbol = f"SENSEX{yy}{mmm}{ce_atm}CE", f"SENSEX{yy}{mmm}{pe_atm}PE"

    print(f"[ALGO] CE ATM:{ce_atm} ({ce_symbol}) | PE ATM:{pe_atm} ({pe_symbol})")
    return ce_symbol, pe_symbol, ce_atm, pe_atm

# ==============================================================================
# 7. 10:30 AM CANDLE — RUNNING DAY (ఈరోజు) మాత్రమే — 5 బ్రోకర్లకూ
# ==============================================================================

def get_running_day_1030_high_low(broker, symbol, access_token, api_key=""):
    """
    ఈరోజు (running day) 10:30–10:44 విండో లో (5 బ్రోకర్లలో ఏదైనా) 1-min
    candles అగ్రిగేట్ చేసి High మరియు Low రెండూ ఇస్తుంది. వెనకటి రోజు లాజిక్ లేదు.
    ⚠️ ఫిక్స్ (2026-10-07): కొత్త ఎంట్రీ లాజిక్‌కి LOW కూడా అవసరం కావడంతో High మరియు Low
    రెండూ ఒకే fetch లో తిరిగి ఇచ్చేలా మార్చాం (ముందు High మాత్రమే ఉండేది, Low కోసం వేరే
    API కాల్ అవసరం అయ్యేది — ఇప్పుడు ఒక్క కాల్‌లోనే పని అవుతుంది).
    Returns: (high, low, error_message_or_None)
    """
    broker = str(broker).lower()
    today_str = today_ist_str()
    instrument_id = _resolve_option_instrument(broker, symbol, access_token, api_key)

    candles, err = _fetch_1min_candles(broker, instrument_id, access_token, api_key, today_str)
    if err:
        return None, None, f"{symbol}: {err}"

    window = [c for c in candles if "10:30" <= c["time"] <= "10:44"]
    if not window:
        return None, None, f"{symbol}: 10:30-10:44 window లో candles దొరకలేదు (మొత్తం {len(candles)} candles వచ్చాయి)."

    high = max(c["high"] for c in window)
    low = min(c["low"] for c in window)
    print(f"[ALGO] 10:30 Candle ({broker}, {symbol}, {len(window)} bars) -> High:{high} Low:{low}")
    return high, low, None

# ==============================================================================
# 8. LIVE LTP FETCH (5 బ్రోకర్లు)
# ==============================================================================

def get_ltp(broker, symbol, access_token, api_key=""):
    broker = str(broker).lower()
    try:
        if broker == "upstox":
            inst_key = get_upstox_instrument_key(symbol, access_token)
            url = f"https://api.upstox.com/v2/market-quote/ltp?instrument_key={inst_key}"
            headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
            res = requests.get(url, headers=headers, timeout=5).json()
            for _, v in res.get("data", {}).items():
                return float(v.get("last_price"))

        elif broker == "zerodha":
            url = f"https://api.kite.trade/quote/ltp?i=BFO:{symbol}"
            headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
            res = requests.get(url, headers=headers, timeout=5).json()
            for _, v in res.get("data", {}).items():
                return float(v.get("last_price"))

        elif broker == "angelone":
            token = resolve_angelone_symboltoken(symbol)
            if not token:
                return None
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/getLtpData"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "Accept": "application/json", "X-PrivateKey": api_key}
            payload = {"exchange": "BFO", "tradingsymbol": symbol, "symboltoken": token}
            res = requests.post(url, json=payload, headers=headers, timeout=5).json()
            return float(res.get("data", {}).get("ltp"))

        elif broker == "dhan":
            sec_id = resolve_dhan_security_id(symbol)
            if not sec_id:
                return None
            url = "https://api.dhan.co/v2/marketfeed/ltp"
            headers = {"access-token": access_token, "client-id": api_key, "Content-Type": "application/json"}
            res = requests.post(url, json={"BSE_FNO": [int(sec_id)]}, headers=headers, timeout=5).json()
            leg = res.get("data", {}).get("BSE_FNO", {})
            for _, v in leg.items():
                return float(v.get("last_price"))

        elif broker == "fyers":
            url = f"https://api-v3.fyers.in/data/quotes?symbols={symbol}"
            headers = {"Authorization": f"{api_key}:{access_token}"}
            res = requests.get(url, headers=headers, timeout=5).json()
            d = res.get("d", [])
            if d:
                return float(d[0].get("v", {}).get("lp"))

    except Exception as e:
        print(f"[{broker.upper()} LTP ERROR] {e}")
    return None

# ==============================================================================
# 9. ORDER PLACEMENT — ENTRY (BREAKOUT SL-BUY)
# ==============================================================================

def place_entry_breakout_order(broker, access_token, api_key, symbol, quantity, entry_trigger_price):
    broker = str(broker).lower()
    trigger_price = round(entry_trigger_price, 2)
    limit_price = round(trigger_price + 0.5, 2)

    if broker == "upstox":
        inst_key = get_upstox_instrument_key(symbol, access_token)
        url = "https://api.upstox.com/v2/order/place"
        headers = {"Accept": "application/json", "Content-Type": "application/json",
                   "Authorization": f"Bearer {access_token}"}
        payload = {"quantity": quantity, "product": "I", "validity": "DAY", "price": limit_price,
                   "trigger_price": trigger_price, "instrument_token": inst_key, "order_type": "SL",
                   "transaction_type": "BUY", "disclosed_quantity": 0, "is_amo": False}

    elif broker == "zerodha":
        url = "https://api.kite.trade/orders/regular"
        headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
        payload = {"tradingsymbol": symbol, "exchange": "BFO", "transaction_type": "BUY",
                   "order_type": "SL", "quantity": quantity, "price": limit_price,
                   "trigger_price": trigger_price, "product": "MIS", "validity": "DAY"}

    elif broker == "angelone":
        token = resolve_angelone_symboltoken(symbol)
        if not token:
            return {"status": "error", "message": f"AngelOne symboltoken not found for {symbol}"}
        url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                   "Accept": "application/json", "X-UserType": "USER", "X-SourceID": "WEB",
                   "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "127.0.0.1",
                   "X-MACAddress": "MAC_ADDRESS", "X-PrivateKey": api_key}
        payload = {"variety": "STOPLOSS", "tradingsymbol": symbol, "symboltoken": token,
                   "transactiontype": "BUY", "exchange": "BFO", "ordertype": "STOPLOSS_LIMIT",
                   "producttype": "INTRADAY", "duration": "DAY", "price": limit_price,
                   "triggerprice": trigger_price, "quantity": quantity}

    elif broker == "dhan":
        url = "https://api.dhan.co/orders"
        headers = {"access-token": access_token, "Content-Type": "application/json", "Accept": "application/json"}
        payload = {"dhanClientId": api_key, "transactionType": "BUY", "exchangeSegment": "BSE_FNO",
                   "productType": "INTRADAY", "orderType": "STOP_LOSS_LIMIT", "validity": "DAY",
                   "tradingSymbol": symbol, "quantity": quantity, "price": limit_price,
                   "triggerPrice": trigger_price}

    elif broker == "fyers":
        url = "https://api-v3.fyers.in/orders/sync"
        headers = {"Authorization": f"{api_key}:{access_token}", "Content-Type": "application/json"}
        payload = {"symbol": symbol, "qty": quantity, "type": 4, "side": 1, "productType": "INTRADAY",
                   "limitPrice": limit_price, "stopPrice": trigger_price, "validity": "DAY",
                   "disclosedQty": 0, "offlineOrder": False}

    else:
        return {"status": "error", "message": "Unsupported Broker"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        res_data = response.json()
        print(f"[{broker.upper()} ENTRY ORDER] {symbol} Trigger:{trigger_price} -> Status:{response.status_code} | {res_data}")
        return res_data
    except Exception as e:
        print(f"[{broker.upper()} ENTRY ORDER FAILED] {e}")
        return {"status": "error", "message": str(e)}


def place_market_entry_order(broker, access_token, api_key, symbol, quantity):
    """
    ⚠️ కొత్త ఎంట్రీ లాజిక్ (2026-10-07) కోసం — ఇక్కడ బ్యాకెండే (పోలింగ్ ద్వారా) ముందే
    బ్రేక్‌అవుట్ జరిగిందని నిర్ధారించుకుని ఈ ఫంక్షన్‌ని పిలుస్తుంది, కాబట్టి బ్రోకర్-సైడ్ పెండింగ్
    SL-BUY ఆర్డర్ అవసరం లేదు — నేరుగా MARKET BUY ఆర్డర్ పెడుతుంది (place_market_exit_order
    లాగే, కానీ BUY వైపు).
    """
    broker = str(broker).lower()
    try:
        if broker == "upstox":
            inst_key = get_upstox_instrument_key(symbol, access_token)
            url = "https://api.upstox.com/v2/order/place"
            headers = {"Accept": "application/json", "Content-Type": "application/json",
                       "Authorization": f"Bearer {access_token}"}
            payload = {"quantity": quantity, "product": "I", "validity": "DAY", "price": 0,
                       "instrument_token": inst_key, "order_type": "MARKET", "transaction_type": "BUY",
                       "disclosed_quantity": 0, "is_amo": False}

        elif broker == "zerodha":
            url = "https://api.kite.trade/orders/regular"
            headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
            payload = {"tradingsymbol": symbol, "exchange": "BFO", "transaction_type": "BUY",
                       "order_type": "MARKET", "quantity": quantity, "product": "MIS", "validity": "DAY"}

        elif broker == "angelone":
            token = resolve_angelone_symboltoken(symbol)
            if not token:
                return {"status": "error", "message": f"AngelOne symboltoken not found for {symbol}"}
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "Accept": "application/json", "X-PrivateKey": api_key}
            payload = {"variety": "NORMAL", "tradingsymbol": symbol, "symboltoken": token,
                       "transactiontype": "BUY", "exchange": "BFO", "ordertype": "MARKET",
                       "producttype": "INTRADAY", "duration": "DAY", "quantity": quantity}

        elif broker == "dhan":
            url = "https://api.dhan.co/orders"
            headers = {"access-token": access_token, "Content-Type": "application/json"}
            payload = {"dhanClientId": api_key, "transactionType": "BUY", "exchangeSegment": "BSE_FNO",
                       "productType": "INTRADAY", "orderType": "MARKET", "validity": "DAY",
                       "tradingSymbol": symbol, "quantity": quantity}

        elif broker == "fyers":
            url = "https://api-v3.fyers.in/orders/sync"
            headers = {"Authorization": f"{api_key}:{access_token}", "Content-Type": "application/json"}
            payload = {"symbol": symbol, "qty": quantity, "type": 2, "side": 1,
                       "productType": "INTRADAY", "validity": "DAY", "offlineOrder": False}
        else:
            return {"status": "error", "message": "Unsupported Broker"}

        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res_data = res.json()
        print(f"[{broker.upper()} MARKET ENTRY ORDER] {symbol} BUY {quantity} -> {res.status_code} | {res_data}")
        return res_data
    except Exception as e:
        print(f"[{broker.upper()} MARKET ENTRY ORDER ERROR] {e}")
        return {"status": "error", "message": str(e)}

# ==============================================================================
# 10. ORDER PLACEMENT — SL (SELL) ORDER
# ==============================================================================

def place_sl_sell_order(broker, access_token, api_key, symbol, quantity, sl_trigger_price):
    broker = str(broker).lower()
    trigger_price = round(sl_trigger_price, 2)
    limit_price = round(trigger_price - 0.5, 2)

    try:
        if broker == "upstox":
            inst_key = get_upstox_instrument_key(symbol, access_token)
            url = "https://api.upstox.com/v2/order/place"
            headers = {"Accept": "application/json", "Content-Type": "application/json",
                       "Authorization": f"Bearer {access_token}"}
            payload = {"quantity": quantity, "product": "I", "validity": "DAY", "price": limit_price,
                       "trigger_price": trigger_price, "instrument_token": inst_key, "order_type": "SL",
                       "transaction_type": "SELL", "disclosed_quantity": 0, "is_amo": False}

        elif broker == "zerodha":
            url = "https://api.kite.trade/orders/regular"
            headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
            payload = {"tradingsymbol": symbol, "exchange": "BFO", "transaction_type": "SELL",
                       "order_type": "SL", "quantity": quantity, "price": limit_price,
                       "trigger_price": trigger_price, "product": "MIS", "validity": "DAY"}

        elif broker == "angelone":
            token = resolve_angelone_symboltoken(symbol)
            if not token:
                return {"status": "error", "message": f"AngelOne symboltoken not found for {symbol}"}
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "Accept": "application/json", "X-PrivateKey": api_key}
            payload = {"variety": "STOPLOSS", "tradingsymbol": symbol, "symboltoken": token,
                       "transactiontype": "SELL", "exchange": "BFO", "ordertype": "STOPLOSS_LIMIT",
                       "producttype": "INTRADAY", "duration": "DAY", "price": limit_price,
                       "triggerprice": trigger_price, "quantity": quantity}

        elif broker == "dhan":
            url = "https://api.dhan.co/orders"
            headers = {"access-token": access_token, "Content-Type": "application/json"}
            payload = {"dhanClientId": api_key, "transactionType": "SELL", "exchangeSegment": "BSE_FNO",
                       "productType": "INTRADAY", "orderType": "STOP_LOSS_LIMIT", "validity": "DAY",
                       "tradingSymbol": symbol, "quantity": quantity, "price": limit_price,
                       "triggerPrice": trigger_price}

        elif broker == "fyers":
            url = "https://api-v3.fyers.in/orders/sync"
            headers = {"Authorization": f"{api_key}:{access_token}", "Content-Type": "application/json"}
            payload = {"symbol": symbol, "qty": quantity, "type": 4, "side": -1, "productType": "INTRADAY",
                       "limitPrice": limit_price, "stopPrice": trigger_price, "validity": "DAY",
                       "disclosedQty": 0, "offlineOrder": False}
        else:
            return {"status": "error", "message": "Unsupported Broker"}

        res = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"[{broker.upper()} SL ORDER PLACED] {symbol} @ Trigger:{trigger_price}")
        return res.json()
    except Exception as e:
        print(f"[{broker.upper()} SL ORDER ERROR] {e}")
        return {"status": "error", "message": str(e)}


def modify_sl_order(broker, order_id, new_trigger_price, access_token, api_key=""):
    broker = str(broker).lower()
    new_trigger_price = round(new_trigger_price, 2)
    new_limit_price = round(new_trigger_price - 0.5, 2)
    try:
        if broker == "upstox":
            url = "https://api.upstox.com/v2/order/modify"
            headers = {"Accept": "application/json", "Content-Type": "application/json",
                       "Authorization": f"Bearer {access_token}"}
            payload = {"order_id": order_id, "trigger_price": new_trigger_price,
                       "price": new_limit_price, "validity": "DAY"}
            requests.put(url, json=payload, headers=headers, timeout=5)

        elif broker == "zerodha":
            url = f"https://api.kite.trade/orders/regular/{order_id}"
            headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
            requests.put(url, data={"trigger_price": new_trigger_price, "price": new_limit_price},
                         headers=headers, timeout=5)

        elif broker == "angelone":
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/modifyOrder"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "X-PrivateKey": api_key}
            payload = {"variety": "STOPLOSS", "orderid": order_id,
                       "triggerprice": new_trigger_price, "price": new_limit_price}
            requests.post(url, json=payload, headers=headers, timeout=5)

        elif broker == "dhan":
            url = f"https://api.dhan.co/orders/{order_id}"
            headers = {"access-token": access_token, "Content-Type": "application/json"}
            requests.put(url, json={"triggerPrice": new_trigger_price, "price": new_limit_price},
                         headers=headers, timeout=5)

        elif broker == "fyers":
            url = "https://api-v3.fyers.in/orders/sync"
            headers = {"Authorization": f"{api_key}:{access_token}", "Content-Type": "application/json"}
            payload = {"id": order_id, "stopPrice": new_trigger_price, "limitPrice": new_limit_price}
            requests.patch(url, json=payload, headers=headers, timeout=5)

        print(f"[{broker.upper()} SL TRAILED] Order:{order_id} New Trigger:{new_trigger_price}")
    except Exception as e:
        print(f"[{broker.upper()} SL MODIFY ERROR] {e}")

# ==============================================================================
# 11. ORDER STATUS CHECK
# ==============================================================================

FILLED_STATUSES = {"COMPLETE", "FILLED", "TRADED", "2"}
# ⚠️ ఆర్డర్ REJECT/CANCEL అయితే (ఉదా: fund/margin సరిపోకపోతే) గుర్తించడానికి.
# బ్రోకర్ status strings వేరుగా ఉండొచ్చు — వాడే ముందు మీ బ్రోకర్ actual response verify చేసుకోండి.
REJECTED_STATUSES = {"REJECTED", "CANCELLED", "CANCELED"}

def get_order_status(broker, order_id, access_token, api_key=""):
    broker = str(broker).lower()
    try:
        if broker == "upstox":
            url = f"https://api.upstox.com/v2/order/details?order_id={order_id}"
            headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
            res = requests.get(url, headers=headers, timeout=5).json()
            d = res.get("data", {})
            return {"status": str(d.get("status", "")).upper(), "avg_price": d.get("average_price")}

        elif broker == "zerodha":
            url = f"https://api.kite.trade/orders/{order_id}"
            headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
            res = requests.get(url, headers=headers, timeout=5).json()
            d = res.get("data", [])
            if d:
                last = d[-1]
                return {"status": str(last.get("status", "")).upper(), "avg_price": last.get("average_price")}

        elif broker == "angelone":
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/getOrderBook"
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "X-PrivateKey": api_key}
            res = requests.get(url, headers=headers, timeout=5).json()
            for o in (res.get("data") or []):
                if o.get("orderid") == order_id:
                    return {"status": str(o.get("status", "")).upper(), "avg_price": o.get("averageprice")}

        elif broker == "dhan":
            url = f"https://api.dhan.co/orders/{order_id}"
            headers = {"access-token": access_token}
            res = requests.get(url, headers=headers, timeout=5).json()
            return {"status": str(res.get("orderStatus", "")).upper(), "avg_price": res.get("averageTradedPrice")}

        elif broker == "fyers":
            url = f"https://api-v3.fyers.in/orders?id={order_id}"
            headers = {"Authorization": f"{api_key}:{access_token}"}
            res = requests.get(url, headers=headers, timeout=5).json()
            d = res.get("orderBook", [])
            if d:
                return {"status": str(d[0].get("status")), "avg_price": d[0].get("tradedPrice")}

    except Exception as e:
        print(f"[{broker.upper()} ORDER STATUS ERROR] {e}")
    return {"status": "UNKNOWN", "avg_price": None}

# ==============================================================================
# 12. TARGET EXIT (MARKET SELL) & CANCEL-ALL
# ==============================================================================

def place_market_exit_order(broker, access_token, api_key, symbol, quantity):
    broker = str(broker).lower()
    try:
        if broker == "upstox":
            inst_key = get_upstox_instrument_key(symbol, access_token)
            url = "https://api.upstox.com/v2/order/place"
            headers = {"Accept": "application/json", "Content-Type": "application/json",
                       "Authorization": f"Bearer {access_token}"}
            payload = {"quantity": quantity, "product": "I", "validity": "DAY", "price": 0,
                       "instrument_token": inst_key, "order_type": "MARKET", "transaction_type": "SELL",
                       "disclosed_quantity": 0, "is_amo": False}

        elif broker == "zerodha":
            url = "https://api.kite.trade/orders/regular"
            headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
            payload = {"tradingsymbol": symbol, "exchange": "BFO", "transaction_type": "SELL",
                       "order_type": "MARKET", "quantity": quantity, "product": "MIS", "validity": "DAY"}

        elif broker == "angelone":
            token = resolve_angelone_symboltoken(symbol)
            if not token:
                return {"status": "error", "message": f"AngelOne symboltoken not found for {symbol}"}
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "Accept": "application/json", "X-PrivateKey": api_key}
            payload = {"variety": "NORMAL", "tradingsymbol": symbol, "symboltoken": token,
                       "transactiontype": "SELL", "exchange": "BFO", "ordertype": "MARKET",
                       "producttype": "INTRADAY", "duration": "DAY", "quantity": quantity}

        elif broker == "dhan":
            url = "https://api.dhan.co/orders"
            headers = {"access-token": access_token, "Content-Type": "application/json"}
            payload = {"dhanClientId": api_key, "transactionType": "SELL", "exchangeSegment": "BSE_FNO",
                       "productType": "INTRADAY", "orderType": "MARKET", "validity": "DAY",
                       "tradingSymbol": symbol, "quantity": quantity}

        elif broker == "fyers":
            url = "https://api-v3.fyers.in/orders/sync"
            headers = {"Authorization": f"{api_key}:{access_token}", "Content-Type": "application/json"}
            payload = {"symbol": symbol, "qty": quantity, "type": 2, "side": -1,
                       "productType": "INTRADAY", "validity": "DAY", "offlineOrder": False}
        else:
            return {"status": "error", "message": "Unsupported Broker"}

        res = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"[{broker.upper()} EXIT ORDER] {symbol} SELL {quantity} -> {res.status_code}")
        return res.json()
    except Exception as e:
        print(f"[{broker.upper()} EXIT ORDER ERROR] {e}")
        return {"status": "error", "message": str(e)}


def cancel_all_broker_orders(broker, access_token, api_key=""):
    broker = str(broker).lower()
    url, headers = "", {}
    if broker == "upstox":
        url = "https://api.upstox.com/v2/order/multi/cancel"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    elif broker == "zerodha":
        url = "https://api.kite.trade/orders"
        headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{access_token}"}
    elif broker == "angelone":
        url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/cancelOrder"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    elif broker == "dhan":
        url = "https://api.dhan.co/orders"
        headers = {"access-token": access_token}
    elif broker == "fyers":
        url = "https://api-v3.fyers.in/orders/sync"
        headers = {"Authorization": f"{api_key}:{access_token}"}

    try:
        response = requests.delete(url, headers=headers, timeout=10)
        print(f"[{broker.upper()} CANCEL EXECUTED] Status: {response.status_code}")
    except Exception as e:
        print(f"[{broker.upper()} CANCEL ERROR] {e}")

# ==============================================================================
# 13. STRATEGY MONITORING LOOP (per-user — phone parameter తీసుకుంటుంది)
# ==============================================================================

def init_watch_leg_state(symbol, low_1030, high_1030):
    """
    ⚠️ కొత్త ఎంట్రీ లాజిక్ (2026-10-07) కోసం leg state — ప్రతి leg (CE/PE) రెండు పాత్రలు
    పోషిస్తుంది: (1) "watch" పాత్ర — తన సొంత 10:30 low ఆధారంగా బ్రేక్‌అవుట్ కోసం
    మానిటర్ అవుతుంది (ఇదే breakout జరిగితే OPPOSITE leg లో ఎంట్రీ తీసుకుంటాం), (2) "trade"
    పాత్ర — ఈ leg నే ఎప్పుడైనా (వేరే leg బ్రేక్ అయినప్పుడు) ఎంట్రీ తీసుకుంటే, దాని
    entry/SL/target వివరాలు ఇక్కడే ఉంటాయి.
    status విలువలు: WATCHING (ఇంకా ఎంట్రీ కాలేదు) -> PENDING_ENTRY -> ENTERED ->
    SL_HIT/TARGET_HIT/TIME_EXIT/ENTRY_FAILED/ENTRY_REJECTED.
    """
    return {
        "symbol": symbol,
        "low_1030": low_1030,
        "high_1030": high_1030,
        "armed": True,              # ఈ leg తన low బ్రేక్ చేస్తే (మళ్ళీ) ట్రిగ్గర్ అవ్వగలదా
        "status": "WATCHING",
        "entry_order_id": None,
        "entry_price": None,
        "sl_order_id": None,
        "current_sl": None,
        "target_price": None,
        "high_since_entry": None,
    }


def wait_for_915_data_and_setup_legs(phone, session, state):
    """
    యూజర్ 9:15 కి ముందే (ఉదా. 9:10కే) Start నొక్కినా, ఈ ఫంక్షన్ 9:15 candle
    పూర్తయ్యేదాకా (broker చార్ట్ ప్రకారం) wait చేసి, పూర్తయిన వెంటనే CE/PE ATM
    strikes లెక్కిస్తుంది. Entry reference కోసం (ఈరోజు 10:30 High) వేరే ఫంక్షన్
    (wait_for_running_day_1030_and_setup_legs) వాడతాం, ఎందుకంటే అది 10:30 AM
    దాటేదాకా తెలియదు.
    అవకాశం మిస్ కాకుండా ఉంటుంది (బటన్ మళ్ళీ నొక్కాల్సిన అవసరం ఉండదు).
    Returns (ce_symbol, pe_symbol) అయితే strikes రెడీ, None అయితే abort అయ్యింది (state["is_active"]=False).
    """
    broker = session["broker"]
    access_token = session["access_token"]
    api_key = session["api_key"]

    print(f"[ALGO] [{phone}] 9:15 candle కోసం wait చేస్తోంది (broker చార్ట్ ప్రకారం పూర్తయ్యేదాకా)...")
    print(f"[ALGO] [{phone}] ప్రస్తుత IST సమయం: {now_ist().strftime('%Y-%m-%d %H:%M:%S')} "
          f"(cutoff: {DATA_WAIT_CUTOFF_TIME})")
    high_915 = low_915 = None
    poll_count = 0

    while state["is_active"]:
        now_str = now_ist().strftime("%H:%M")

        # ⚠️ ఫిక్స్: 09:15-09:29 విండో 09:30 కి ముందే ఇంకా పూర్తి కాలేదు (candle incomplete) —
        # ముందు fetch చేస్తే తప్పు High/Low (తప్పు PE/CE strike కి కారణం) వస్తుంది.
        # 09:30 దాటేదాకా ఫెచ్ అసలు ట్రై చేయకుండా ఆపుతాం.
        if now_str < "09:30":
            time.sleep(min(DATA_WAIT_POLL_SECONDS * 6, 30))
            continue

        high_915, low_915, err = fetch_915_high_low(broker, access_token, api_key)
        if high_915 is not None and low_915 is not None:
            break

        poll_count += 1
        if err and poll_count % 12 == 1:  # ప్రతి ~60 సెకన్లకు ఒకసారి (12 x 5 sec) App లో alert పెడతాం
            with state_lock:
                state["trade_history"].append({
                    "leg": "-", "event": "DATA_FETCH_RETRYING",
                    "message": f"9:15 candle కోసం ప్రయత్నిస్తోంది... కారణం: {err}",
                    "time": now_str,
                })

        if now_str >= DATA_WAIT_CUTOFF_TIME:
            with state_lock:
                state["is_active"] = False
                state["phase"] = "STOPPED"
                state["trade_history"].append({
                    "leg": "-", "event": "ABORTED",
                    "message": f"మార్కెట్ ముగిసింది ({DATA_WAIT_CUTOFF_TIME}) — ఈరోజు 9:15 candle డేటా దొరకలేదు. "
                               f"చివరి కారణం: {err or 'తెలియదు'}",
                    "time": now_str,
                })
            print(f"[ALGO] [{phone}] 9:15 data cutoff దాటింది, abort.")
            return None

        time.sleep(DATA_WAIT_POLL_SECONDS)

    if not state["is_active"]:
        # యూజర్ wait చేస్తున్నప్పుడే Stop నొక్కి ఉండొచ్చు
        return None

    ce_symbol, pe_symbol, ce_atm, pe_atm = calculate_atm_strikes(high_915, low_915, broker)
    now_str = now_ist().strftime("%H:%M")
    with state_lock:
        state["spot_915_high"] = high_915
        state["spot_915_low"] = low_915
        state["trade_history"].append({
            "leg": "-", "event": "ATM_STRIKES_READY",
            "message": f"9:15 candle ఆధారంగా ATM strikes ఎంచుకున్నాం — CE:{ce_symbol} (ATM {ce_atm}) | "
                       f"PE:{pe_symbol} (ATM {pe_atm}). ఇప్పుడు ఈరోజు 10:30 candle కోసం wait చేస్తుంది.",
            "time": now_str,
        })
    print(f"[ALGO] [{phone}] ATM strikes ready -> CE:{ce_symbol} PE:{pe_symbol}. Running-day 10:30 high కోసం wait...")
    return ce_symbol, pe_symbol


def wait_for_running_day_1030_and_setup_legs(phone, session, state, ce_symbol, pe_symbol):
    """
    ఈరోజు (running day) 10:30 AM candle పూర్తయ్యేదాకా (broker చార్ట్ ప్రకారం) ఇక్కడ wait
    చేస్తుంది. ⚠️ ఫిక్స్ (2026-10-07, కొత్త ఎంట్రీ లాజిక్): ఇప్పుడు High తో పాటు LOW కూడా
    కావాలి — CE/PE ఆప్షన్ల సొంత 10:30 LOW కన్నా 5 పాయింట్లు కిందికి ఏదో ఒకటి బ్రేక్ అయితే,
    దాని OPPOSITE ఆప్షన్‌లో ఎంట్రీ తీసుకుంటాం (పాత "High+3 breakout, SAME leg" లాజిక్‌కి
    బదులు).
    Returns True అయితే legs రెడీ, False అయితే abort.
    """
    broker = session["broker"]
    access_token = session["access_token"]
    api_key = session["api_key"]
    poll_count = 0

    while state["is_active"]:
        now_str = now_ist().strftime("%H:%M")

        if now_str < "10:30":
            # 10:30 ఇంకా కాలేదు — అనవసరంగా API ని తరచుగా కొట్టం, తక్కువ frequency లో wait
            time.sleep(min(DATA_WAIT_POLL_SECONDS * 6, 30))
            continue

        ce_high, ce_low, ce_err = get_running_day_1030_high_low(broker, ce_symbol, access_token, api_key)
        pe_high, pe_low, pe_err = get_running_day_1030_high_low(broker, pe_symbol, access_token, api_key)

        if ce_low is not None and pe_low is not None:
            now_str = now_ist().strftime("%H:%M")
            with state_lock:
                state["legs"]["CE"] = init_watch_leg_state(ce_symbol, ce_low, ce_high)
                state["legs"]["PE"] = init_watch_leg_state(pe_symbol, pe_low, pe_high)
                state["phase"] = "TRADING"
                state["trade_history"].append({
                    "leg": "-", "event": "STRIKES_READY",
                    "message": f"ఈరోజు 10:30 Low ఆధారంగా మానిటరింగ్ రెడీ — "
                               f"CE:{ce_symbol} Low:{ce_low} (High:{ce_high}) | "
                               f"PE:{pe_symbol} Low:{pe_low} (High:{pe_high}). "
                               f"ఏదైనా ఆప్షన్ తన Low కన్నా {BREAKOUT_BREAK_POINTS} పాయింట్లు కిందికి బ్రేక్ "
                               f"అయితే, ఆ ఆప్షన్‌కి బదులు OPPOSITE ఆప్షన్‌లో ఎంట్రీ తీసుకుంటాం.",
                    "time": now_str,
                })
            print(f"[ALGO] [{phone}] Running-day 10:30 ready -> CE Low:{ce_low} PE Low:{pe_low}")
            return True

        poll_count += 1
        if (ce_err or pe_err) and poll_count % 12 == 1:
            with state_lock:
                state["trade_history"].append({
                    "leg": "-", "event": "DATA_FETCH_RETRYING",
                    "message": f"10:30 candle కోసం ప్రయత్నిస్తోంది... కారణం: {ce_err or pe_err}",
                    "time": now_str,
                })

        if now_str >= ENTRY_REF_WAIT_CUTOFF_TIME:
            with state_lock:
                state["is_active"] = False
                state["phase"] = "STOPPED"
                state["trade_history"].append({
                    "leg": "-", "event": "ABORTED",
                    "message": f"మార్కెట్ ముగిసింది ({ENTRY_REF_WAIT_CUTOFF_TIME}) — ఈరోజు 10:30 candle డేటా దొరకలేదు. "
                               f"కారణం: {ce_err or pe_err or 'తెలియదు'}",
                    "time": now_str,
                })
            print(f"[ALGO] [{phone}] 10:30 entry-ref cutoff దాటింది, abort.")
            return False

        time.sleep(DATA_WAIT_POLL_SECONDS)

    return False


def run_strategy_loop(phone):
    """
    ⚠️ మార్పు (2026-10-08, యూజర్ కోరిక ప్రకారం): ఇది ఇక ఆటోమేటిక్‌గా బ్రోకర్ ఆర్డర్లు
    పెట్టదు — కేవలం CE/PE strikes, Entry, SL, Target సిగ్నల్స్ లెక్కించి Live Trade
    Alerts లో చూపిస్తుంది. యూజర్ ఆ సిగ్నల్ చూసి తన బ్రోకర్ యాప్‌లో మాన్యువల్‌గా ఆర్డర్
    పెట్టుకోవాలి. దీనివల్ల ఆర్డర్-ప్లేసింగ్ APIలకు ఉన్న static-IP/SEBI ఆంక్షలు (Upstox
    algo-trading కి పెట్టిన రూల్ లాంటివి) ఇక వర్తించవు — కేవలం read-only market-data
    (candles/LTP) మాత్రమే కావాలి, అది ఏ బ్రోకర్ అయినా static IP లేకుండానే పని చేస్తుంది.
    """
    print(f"[ALGO] [{phone}] Live Signal Engine Active (Manual Entry Mode)...")
    session = user_sessions.get(phone)
    state = trading_states.get(phone)
    if not session or not state:
        print(f"[ALGO] [{phone}] session/state missing, aborting loop.")
        return

    broker = session["broker"]
    access_token, api_key = session["access_token"], session["api_key"]

    # ---- Phase 1: 9:15 candle కోసం wait చేసి, legs సెటప్ చేయడం ----
    strikes = wait_for_915_data_and_setup_legs(phone, session, state)
    if not strikes:
        active_threads.pop(phone, None)
        return
    ce_symbol, pe_symbol = strikes

    if not wait_for_running_day_1030_and_setup_legs(phone, session, state, ce_symbol, pe_symbol):
        active_threads.pop(phone, None)
        return

    while state["is_active"]:
        now_str = now_ist().strftime("%H:%M")

        if now_str >= SQUARE_OFF_TIME:
            print(f"[ALGO] [{phone}] 3:10 PM reached. Signal session ending...")
            with state_lock:
                for leg_name, leg in state["legs"].items():
                    if leg.get("status") == "SIGNAL_ACTIVE":
                        leg["status"] = "TIME_EXIT"
                        state["trade_history"].append({
                            "leg": leg_name, "event": "TIME_EXIT_SIGNAL",
                            "message": f"మార్కెట్ ముగిసింది (3:10 PM) — {leg_name} ఇంకా పొజిషన్‌లో ఉంటే "
                                       f"మాన్యువల్‌గా మీ బ్రోకర్ యాప్‌లో స్క్వేర్-ఆఫ్ చేసుకోండి.",
                            "time": now_str, "symbol": leg["symbol"],
                        })
                state["is_active"] = False
            break

        # ------------------------------------------------------------------
        # ఎంట్రీ సిగ్నల్ లాజిక్: ఏ leg లోనూ సిగ్నల్ యాక్టివ్‌గా లేకపోతే, మరియు ఇంకా
        # MAX_ENTRY_ATTEMPTS మిగిలి ఉంటే — CE/PE రెండింటి సొంత 10:30 Low ని
        # BREAKOUT_BREAK_POINTS (5) పాయింట్లు కిందికి బ్రేక్ అవుతున్నాయేమో చూస్తాం.
        # ఏదైనా బ్రేక్ అయితే, దానికి బదులు దాని OPPOSITE leg లో ఎంట్రీ సిగ్నల్ ఇస్తాం
        # (నిజమైన ఆర్డర్ పెట్టం — యూజరే మాన్యువల్‌గా ఎంటర్ అవ్వాలి).
        # ------------------------------------------------------------------
        any_signal_active = any(leg.get("status") == "SIGNAL_ACTIVE" for leg in state["legs"].values())

        if not any_signal_active and state["attempts_used"] < MAX_ENTRY_ATTEMPTS:
            for watch_name, opp_name in (("CE", "PE"), ("PE", "CE")):
                watch_leg = state["legs"][watch_name]
                if watch_leg["status"] not in ("WATCHING",):
                    continue

                ltp_watch = get_ltp(broker, watch_leg["symbol"], access_token, api_key)
                if ltp_watch is None:
                    continue

                break_level = round(watch_leg["low_1030"] - BREAKOUT_BREAK_POINTS, 2)

                if not watch_leg["armed"]:
                    # SL సిగ్నల్ తర్వాత తిరిగి ట్రిగ్గర్ అవ్వాలంటే ముందు ధర ఈ break_level
                    # పైకి recover అయ్యి ఉండాలి (అప్పుడే "కొత్త" బ్రేక్‌అవుట్ గా లెక్క).
                    if ltp_watch > break_level:
                        with state_lock:
                            watch_leg["armed"] = True
                    continue

                if ltp_watch <= break_level:
                    opp_leg = state["legs"][opp_name]
                    entry_price = get_ltp(broker, opp_leg["symbol"], access_token, api_key)
                    if entry_price is None:
                        continue  # తర్వాతి poll cycle లో మళ్ళీ ప్రయత్నిస్తుంది

                    with state_lock:
                        watch_leg["armed"] = False
                        state["attempts_used"] += 1
                        attempt_no = state["attempts_used"]

                        opp_leg["entry_price"] = entry_price
                        opp_leg["high_since_entry"] = entry_price
                        opp_leg["current_sl"] = round(entry_price - REVERSAL_SL_POINTS, 2)
                        opp_leg["target_price"] = round(entry_price + session.get("target_points", FULL_TARGET_POINTS), 2)
                        opp_leg["status"] = "SIGNAL_ACTIVE"

                        state["trade_history"].append({
                            "leg": watch_name, "event": "BREAKOUT_DETECTED",
                            "message": f"{watch_name} ({watch_leg['symbol']}) తన 10:30 Low "
                                       f"({watch_leg['low_1030']}) కన్నా {BREAKOUT_BREAK_POINTS} పాయింట్లు "
                                       f"కిందికి బ్రేక్ అయింది (LTP:{ltp_watch}).",
                            "time": now_str,
                        })
                        state["trade_history"].append({
                            "leg": opp_name, "event": "ENTRY_SIGNAL",
                            "message": f"🟢 ఎంట్రీ సిగ్నల్! {opp_name} ({opp_leg['symbol']}) లో ధర "
                                       f"₹{entry_price} వద్ద మాన్యువల్‌గా BUY చేసుకోండి — "
                                       f"SL: ₹{opp_leg['current_sl']} | Target: ₹{opp_leg['target_price']} "
                                       f"(ప్రయత్నం {attempt_no}/{MAX_ENTRY_ATTEMPTS}).",
                            "price": entry_price, "time": now_str,
                        })
                    print(f"[ALGO] [{phone}] {watch_name} broke its 10:30 low by {BREAKOUT_BREAK_POINTS}pts "
                          f"(LTP:{ltp_watch}) -> ENTRY SIGNAL on {opp_name} @ {entry_price} (attempt {attempt_no})")
                    break  # ఈ poll cycle కి ఒక్క ట్రిగ్గర్ మాత్రమే

        # ------------------------------------------------------------------
        # యాక్టివ్ సిగ్నల్ మానిటరింగ్: Trailing SL, Target, SL — అన్నీ లెక్కింపు మాత్రమే,
        # ఏ బ్రోకర్ ఆర్డర్ కాల్ లేదు. యూజర్ తన సొంత పొజిషన్ ని ఈ సిగ్నల్స్ ఆధారంగా మాన్యువల్‌గా
        # మేనేజ్ చేసుకోవాలి.
        # ------------------------------------------------------------------
        for leg_name, leg in state["legs"].items():
            if leg["status"] != "SIGNAL_ACTIVE":
                continue

            ltp = get_ltp(broker, leg["symbol"], access_token, api_key)
            if ltp is None:
                continue

            if ltp >= leg["target_price"]:
                print(f"[ALGO] [{phone}] {leg_name} TARGET SIGNAL @ {ltp}")
                with state_lock:
                    leg["status"] = "TARGET_HIT"
                    state["trade_history"].append({
                        "leg": leg_name, "event": "TARGET_SIGNAL",
                        "message": f"🎯 టార్గెట్ సిగ్నల్! {leg_name} ధర ₹{ltp} కి చేరింది (Target: "
                                   f"₹{leg['target_price']}) — మాన్యువల్‌గా స్క్వేర్-ఆఫ్ చేసుకోండి. "
                                   f"ఈరోజుకి స్ట్రాటజీ ఆగిపోతుంది.",
                        "price": ltp, "time": now_str,
                    })
                    state["is_active"] = False
                break

            if ltp > leg["high_since_entry"]:
                with state_lock:
                    leg["high_since_entry"] = ltp
                    steps = math.floor((leg["high_since_entry"] - leg["entry_price"]) / TRAIL_STEP_POINTS)
                    new_sl = round(leg["entry_price"] - REVERSAL_SL_POINTS + steps * TRAIL_SL_MOVE_POINTS, 2)
                    if new_sl > leg["current_sl"]:
                        leg["current_sl"] = new_sl
                        state["trade_history"].append({
                            "leg": leg_name, "event": "SL_TRAILED",
                            "message": f"🔼 {leg_name} SL ట్రైల్ అయింది -> ₹{new_sl} (LTP:₹{ltp}). "
                                       f"మాన్యువల్‌గా మీ SL ఆర్డర్ అప్‌డేట్ చేసుకోండి.",
                            "time": now_str,
                        })
                        print(f"[ALGO] [{phone}] {leg_name} SL Trailed -> {new_sl} (LTP:{ltp})")

            if ltp <= leg["current_sl"]:
                with state_lock:
                    leg["status"] = "SL_HIT"
                    state["sl_hit_count"] += 1
                    state["trade_history"].append({
                        "leg": leg_name, "event": "SL_SIGNAL",
                        "message": f"🔴 SL సిగ్నల్ (reversal)! {leg_name} ధర ₹{ltp} కి పడింది (SL: "
                                   f"₹{leg['current_sl']}) — మాన్యువల్‌గా ఎగ్జిట్ చేసుకోండి.",
                        "price": ltp, "time": now_str,
                    })

                    if state["attempts_used"] >= MAX_ENTRY_ATTEMPTS:
                        state["is_active"] = False
                        state["phase"] = "STOPPED"
                        state["trade_history"].append({
                            "leg": "-", "event": "MAX_ATTEMPTS_REACHED",
                            "message": f"మొత్తం {MAX_ENTRY_ATTEMPTS} ఎంట్రీ ప్రయత్నాలు పూర్తయ్యాయి — "
                                       f"ఈరోజుకి ఇక కొత్త సిగ్నల్స్ ఇవ్వము. స్ట్రాటజీ ఆగిపోయింది.",
                            "time": now_str,
                        })
                    else:
                        leg["status"] = "WATCHING"
                        leg["entry_price"] = None
                        leg["current_sl"] = None
                        leg["target_price"] = None
                        leg["high_since_entry"] = None
                print(f"[ALGO] [{phone}] {leg_name} SL SIGNAL @ {ltp} (reversal) — "
                      f"attempts_used:{state['attempts_used']}/{MAX_ENTRY_ATTEMPTS}")

        if not state["is_active"]:
            print(f"[ALGO] [{phone}] Strategy Stopped.")
            break

        time.sleep(MONITOR_POLL_SECONDS)

    active_threads.pop(phone, None)

# ==============================================================================
# 14. API ENDPOINTS — APPROVAL / ADMIN
# ==============================================================================

@app.route('/upstox-exchange-token', methods=['POST', 'OPTIONS'])
def upstox_exchange_token():
    """
    ⚠️ Upstox access_token ని రోజూ మాన్యువల్‌గా Postman వంటి టూల్‌తో generate చేసుకోవాల్సిన
    అవసరం లేకుండా — ఈ ఎండ్‌పాయింట్ ఫ్రంటెండ్ నుండి వచ్చిన authorization 'code' ని
    Upstox తో server-side (CORS సమస్య లేకుండా) exchange చేసి access_token తిరిగి ఇస్తుంది.
    client_secret ఇక్కడ ఎక్కడా స్టోర్ చేయం — కేవలం ఈ ఒక్క రిక్వెస్ట్ కోసమే వాడతాం.
    """
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    data = request.json or {}
    client_id = data.get("client_id", "").strip()
    client_secret = data.get("client_secret", "").strip()
    redirect_uri = data.get("redirect_uri", "").strip()
    code = data.get("code", "").strip()

    if not all([client_id, client_secret, redirect_uri, code]):
        return jsonify({"status": "error", "message": "client_id, client_secret, redirect_uri, code అన్నీ అవసరం"}), 400

    try:
        url = "https://api.upstox.com/v2/login/authorization/token"
        headers = {"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        res = requests.post(url, headers=headers, data=payload, timeout=15)
        try:
            res_json = res.json()
        except ValueError:
            res_json = {"raw_text": res.text}

        if res.status_code == 200 and res_json.get("access_token"):
            print(f"[UPSTOX LOGIN] access_token generate అయింది (client_id:{client_id[:8]}...)")
            return jsonify({"status": "success", "access_token": res_json["access_token"]}), 200

        print(f"[UPSTOX LOGIN ERROR] status:{res.status_code} body:{res_json}")
        return jsonify({"status": "error", "message": f"Upstox token exchange failed: {res_json}"}), 400
    except Exception as e:
        print(f"[UPSTOX LOGIN EXCEPTION] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/request-approval', methods=['POST', 'OPTIONS'])
def request_approval():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    data = request.json or {}
    phone = data.get("phone")
    # ⚠️ 2026-10-08: ఇక రెండు ప్లాన్లు లేవు — ఒకే ₹2,499 ప్లాన్ (FULL) మాత్రమే.
    plan = "FULL"
    if not phone:
        return jsonify({"status": "error"}), 400

    existing = db_get_user(phone)
    if existing and existing.get("status") == "APPROVED":
        return jsonify({"status": "success", "message": "Already approved"}), 200

    db_upsert_user(phone, "PENDING", None, plan=plan)
    return jsonify({"status": "success"}), 200


@app.route('/get-pending-requests', methods=['GET'])
def get_pending_requests():
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    items = db_list_pending()
    return jsonify([{"phone": i["phone"], "plan": i["plan"], "time": "Just now"} for i in items]), 200


@app.route('/admin-action', methods=['POST', 'OPTIONS'])
def admin_action():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.json or {}
    phone = data.get("phone")
    action = data.get("action")
    if not phone or not db_get_user(phone):
        return jsonify({"status": "error"}), 400

    if action == "APPROVE":
        # plan=None -> ఇప్పటికే ఉన్న plan (ఎప్పుడూ FULL) అలానే ఉంటుంది
        db_upsert_user(phone, "APPROVED", now_ist().isoformat())
    else:
        db_upsert_user(phone, "REJECTED", None)
    return jsonify({"status": "success"}), 200


@app.route('/check-user-status', methods=['GET'])
def check_user_status():
    phone = request.args.get("phone")
    rec = db_get_user(phone) if phone else None

    if not rec:
        return jsonify({"status": "NOT_FOUND", "expired": False, "days_left": None}), 200

    status = rec.get("status")
    approved_at = rec.get("approved_at")
    plan = rec.get("plan") or "FULL"

    if status != "APPROVED" or not approved_at:
        return jsonify({"status": status, "expired": False, "days_left": None, "plan": plan}), 200

    approved_dt = datetime.fromisoformat(approved_at)
    days_passed = _days_since_ist(approved_dt)
    days_left = SUBSCRIPTION_DAYS - days_passed
    expired = days_left <= 0

    return jsonify({
        "status": "APPROVED",
        "approved_at": approved_at,
        "days_left": max(days_left, 0),
        "expired": expired,
        "plan": plan,
    }), 200

# ==============================================================================
# 15. API ENDPOINTS — TRADING (per-phone)
# ==============================================================================

@app.route('/start-strategy', methods=['POST', 'OPTIONS'])
def start_strategy():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    data = request.json or {}
    phone = data.get("phone")
    if not phone:
        return jsonify({"status": "error", "message": "phone అవసరం"}), 400

    # ఈ యూజర్ approved & active subscription లో ఉన్నారో లేదో backend-side verify
    rec = db_get_user(phone)
    if not rec or rec.get("status") != "APPROVED":
        return jsonify({"status": "error", "message": "Not approved"}), 403
    approved_dt = datetime.fromisoformat(rec["approved_at"])
    if _days_since_ist(approved_dt) >= SUBSCRIPTION_DAYS:
        return jsonify({"status": "error", "message": "Subscription expired"}), 403

    with state_lock:
        if trading_states.get(phone, {}).get("is_active"):
            return jsonify({"status": "error", "message": "ఇప్పటికే ఈ యూజర్ కోసం strategy running ఉంది"}), 409

    # ⚠️ 2026-10-08: ఇక ఒకే ₹2,499 ప్లాన్ — Beginner lot-cap నియమం తీసేశాం.
    plan = "FULL"
    requested_lots = int(data.get("lots", 1))

    broker = data.get("broker", "upstox").lower()
    # ⚠️ ప్రస్తుతం debugging focus కోసం Upstox మరియు Dhan మాత్రమే — మిగతా బ్రోకర్లు
    # (Zerodha, AngelOne, Fyers) live verify అయ్యేదాకా తాత్కాలికంగా ఆపేసాం.
    SUPPORTED_BROKERS = {"upstox", "dhan"}
    if broker not in SUPPORTED_BROKERS:
        return jsonify({
            "status": "error",
            "message": f"ప్రస్తుతం '{broker}' సపోర్ట్ చేయడం లేదు. Upstox లేదా Dhan వాడండి."
        }), 400
    # ⚠️ ఒకే ప్లాన్ కాబట్టి Target ఎప్పుడూ 100 points.
    plan_target_points = FULL_TARGET_POINTS
    session = {
        "broker": broker,
        "access_token": data.get("access_token") or data.get("api_secret", ""),
        "api_key": data.get("api_key", ""),
        "client_id": data.get("client_id", ""),
        "lots": requested_lots,
        "lot_size": int(data.get("lot_size", 10)),
        "plan": plan,
        "target_points": plan_target_points,
    }

    # ⚠️ Fix: "already active" చెక్ మరియు thread spawn ఇప్పుడు ఒకే లాక్ కింద atomic గా
    # జరుగుతాయి — ఇంతకుముందు చెక్ చేసి లాక్ విడిచిపెట్టేసి, ఆ తర్వాతే thread create
    # చేసేవాళ్ళం. ఆ మధ్య గ్యాప్‌లో (ఉదా. Render cold-start వల్ల browser accidentally
    # రెండుసార్లు request పంపితే) రెండు threads spawn అయ్యే అవకాశం ఉండేది — అదే మనం
    # logs లో చూసిన 'ఒకే సెకన్‌లో అనేక identical error lines' కి కారణం కావొచ్చు.
    with state_lock:
        if trading_states.get(phone, {}).get("is_active"):
            return jsonify({"status": "error", "message": "ఇప్పటికే ఈ యూజర్ కోసం strategy running ఉంది"}), 409

        user_sessions[phone] = session
        state = new_trading_state()
        state["is_active"] = True
        trading_states[phone] = state

    # ⬇️ ఇక్కడ synchronously 9:15/10:30 డేటా కోసం wait చేయం (request hang అవకుండా).
    # బదులుగా వెంటనే thread మొదలుపెడతాం — అది 9:15 candle పూర్తయ్యేదాకా (broker చార్ట్
    # ప్రకారం) wait చేసి, పూర్తయిన వెంటనే entry breakout ఆర్డర్లు వెంటనే పెడుతుంది.
    # ఇలా చేయడం వల్ల యూజర్ 9:10కే Start నొక్కినా ఒక్క entry అవకాశం కూడా మిస్ కాదు.
    strategy_thread = threading.Thread(target=run_strategy_loop, args=(phone,))
    strategy_thread.daemon = True
    strategy_thread.start()
    active_threads[phone] = strategy_thread

    return jsonify({
        "status": "success",
        "message": f"Strategy Queued for Broker: {broker.upper()}. 9:15 candle పూర్తయ్యేదాకా wait చేస్తుంది.",
        "phase": "WAITING_FOR_915_DATA",
        "plan": plan,
        "target_points": plan_target_points,
        "trail_step_points": TRAIL_STEP_POINTS,
        "trail_sl_move_points": TRAIL_SL_MOVE_POINTS,
        "initial_sl_points": REVERSAL_SL_POINTS,
        "breakout_break_points": BREAKOUT_BREAK_POINTS,
        "max_entry_attempts": MAX_ENTRY_ATTEMPTS,
    }), 200


@app.route('/stop-strategy', methods=['POST', 'OPTIONS'])
def stop_strategy():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    data = request.json or {}
    phone = data.get("phone")
    if not phone:
        return jsonify({"status": "error", "message": "phone అవసరం"}), 400

    session = user_sessions.get(phone)
    state = trading_states.get(phone)
    if not session or not state:
        return jsonify({"status": "success", "message": "No active session for this phone."}), 200

    was_active = state["is_active"]
    with state_lock:
        state["is_active"] = False

    if was_active:
        broker, access_token, api_key = session["broker"], session["access_token"], session["api_key"]
        quantity = session["lots"] * session["lot_size"]
        cancel_all_broker_orders(broker, access_token, api_key)
        for leg_name, leg in state["legs"].items():
            if leg.get("status") == "ENTERED":
                place_market_exit_order(broker, access_token, api_key, leg["symbol"], quantity)
                leg["status"] = "MANUAL_STOP"
                state["trade_history"].append(
                    {"leg": leg_name, "event": "MANUAL_STOP", "time": now_ist().strftime("%H:%M")})

    return jsonify({"status": "success", "message": "Strategy stopped & orders cancelled."}), 200


@app.route('/get-history', methods=['GET'])
def get_history():
    phone = request.args.get("phone")
    state = trading_states.get(phone) if phone else None
    if not state:
        return jsonify({
            "state": {"is_active": False, "phase": "IDLE", "sl_hit_count": 0, "legs": {"CE": {}, "PE": {}}},
            "history": [],
        }), 200

    return jsonify({
        "state": {
            "is_active": state["is_active"],
            "phase": state.get("phase", "TRADING"),
            "sl_hit_count": state["sl_hit_count"],
            "legs": state["legs"],
            "spot_915_high": state.get("spot_915_high"),
            "spot_915_low": state.get("spot_915_low"),
            "attempts_used": state.get("attempts_used", 0),
            "max_attempts": MAX_ENTRY_ATTEMPTS,
        },
        "history": state["trade_history"],
    }), 200

# ==============================================================================
# 16. SERVER INITIALIZATION
# ==============================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

