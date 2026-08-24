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
import csv
import io
import math
import time
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==============================================================================
# 1. STRATEGY CONSTANTS
# ==============================================================================

TARGET_POINTS = 100
TRAIL_STEP_POINTS = 30
TRAIL_SL_MOVE_POINTS = 15
INITIAL_SL_POINTS = 15
ENTRY_BUFFER_POINTS = 3
MONITOR_POLL_SECONDS = 2
SQUARE_OFF_TIME = "15:10"
SUBSCRIPTION_DAYS = 30
DATA_WAIT_CUTOFF_TIME = "09:45"   # 9:15 candle కోసం ఇంతవరకే wait చేస్తుంది, ఆ తర్వాత abort
DATA_WAIT_POLL_SECONDS = 5        # ఎంత తరచుగా 9:15 candle దొరికిందా అని రీ-చెక్ చేయాలి

SENSEX_INDEX_KEY_UPSTOX = "BSE_INDEX|SENSEX"

# ⚠️ దయచేసి ఇది env var గా Render లో సెట్ చేయండి (Settings → Environment).
# సెట్ చేయకపోతే fallback డిఫాల్ట్ వాడుతుంది — production లో ఇది సురక్షితం కాదు.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "merababa@123")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensex_edge.db")

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
            approved_at TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


def db_get_user(phone):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return dict(row) if row else None


def db_upsert_user(phone, status, approved_at=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO users (phone, status, approved_at) VALUES (?, ?, ?)
        ON CONFLICT(phone) DO UPDATE SET status = excluded.status, approved_at = excluded.approved_at
    """, (phone, status, approved_at))
    conn.commit()
    conn.close()


def db_list_pending():
    conn = get_db()
    rows = conn.execute("SELECT phone FROM users WHERE status = 'PENDING'").fetchall()
    conn.close()
    return [r["phone"] for r in rows]

# ==============================================================================
# 3. ADMIN AUTH — password ఇక్కడే ఉంటుంది, frontend కి ఎప్పుడూ పంపబడదు
# ==============================================================================

admin_sessions = set()  # valid session tokens (in-memory; restart అయితే admin మళ్ళీ login కావాలి)


def is_admin_request():
    token = request.headers.get("X-Admin-Token", "")
    return token in admin_sessions


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
    }

# ==============================================================================
# 5. EXPIRY & INSTRUMENT RESOLUTION
# ==============================================================================

def get_next_expiry_date():
    today = datetime.now()
    days_ahead = (3 - today.weekday()) % 7  # 3 = Thursday
    if days_ahead == 0 and today.hour >= 15:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def get_upstox_instrument_key(trading_symbol, access_token):
    url = f"https://api.upstox.com/v2/instruments/search?query={trading_symbol}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        data = res.get("data", [])
        if data:
            for item in data:
                if item.get("trading_symbol") == trading_symbol or item.get("short_name") == trading_symbol:
                    return item.get("instrument_key")
            return data[0].get("instrument_key")
    except Exception as e:
        print(f"[UPSTOX SEARCH ERROR] {e}")
    return trading_symbol


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

# ==============================================================================
# 6. 9:15 AM CANDLE (INDEX) -> ATM STRIKE SELECTION
#    ⚠️ ఇప్పుడు live data దొరకకపోతే fallback వాడదు — None రిటర్న్ చేస్తుంది,
#    caller (start_strategy) దాన్ని చూసి స్ట్రాటజీ మొదలుపెట్టదు.
# ==============================================================================

def fetch_915_high_low(broker, access_token):
    broker = str(broker).lower()
    today_str = datetime.now().strftime("%Y-%m-%d")

    if broker == "upstox":
        url = f"https://api.upstox.com/v2/historical-candle/{SENSEX_INDEX_KEY_UPSTOX}/15minute/{today_str}/{today_str}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
        try:
            res = requests.get(url, headers=headers, timeout=10).json()
            candles = res.get("data", {}).get("candles", [])
            for c in candles:
                if "09:15:00" in c[0]:
                    high, low = float(c[2]), float(c[3])
                    print(f"[ALGO] 9:15 Candle -> High:{high} Low:{low}")
                    return high, low
        except Exception as e:
            print(f"[ERROR] 9:15 Candle Fetch Failed: {e}")
    else:
        print(f"[WARNING] {broker} కోసం 9:15 index-candle API ఇంకా ఇంప్లిమెంట్ కాలేదు.")

    print("[ERROR] 9:15 candle live data దొరకలేదు — స్ట్రాటజీ మొదలుపెట్టం.")
    return None, None


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
        ce_symbol, pe_symbol = f"SENSEX{ce_atm}CE", f"SENSEX{pe_atm}PE"

    print(f"[ALGO] CE ATM:{ce_atm} ({ce_symbol}) | PE ATM:{pe_atm} ({pe_symbol})")
    return ce_symbol, pe_symbol, ce_atm, pe_atm

# ==============================================================================
# 7. 10:30 AM CANDLE (PREVIOUS DAY -> RUNNING DAY, NO NUMERIC FALLBACK)
# ==============================================================================

def get_1030_candle_high(broker, symbol, access_token, target_date):
    broker = str(broker).lower()
    if broker == "upstox":
        inst_key = get_upstox_instrument_key(symbol, access_token)
        url = f"https://api.upstox.com/v2/historical-candle/{inst_key}/15minute/{target_date}/{target_date}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
        try:
            res = requests.get(url, headers=headers, timeout=10).json()
            candles = res.get("data", {}).get("candles", [])
            for c in candles:
                if "10:30:00" in c[0]:
                    return float(c[2])
        except Exception as e:
            print(f"[ERROR] 10:30 candle ({target_date}) fetch failed: {e}")
    else:
        print(f"[WARNING] {broker} కోసం 10:30 candle API ఇంకా ఇంప్లిమెంట్ కాలేదు.")
    return None


def get_entry_reference_high(broker, symbol, access_token):
    """
    Returns: (reference_price_or_None, source)
    source: PREVIOUS_DAY / RUNNING_DAY / UNAVAILABLE (ఇక FALLBACK numeric విలువ లేదు)
    """
    prev_day = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_high = get_1030_candle_high(broker, symbol, access_token, prev_day)
    if prev_high is not None:
        print(f"[ALGO] {symbol}: వెనకటి రోజు ({prev_day}) 10:30 High = {prev_high} వాడుతున్నాం.")
        return prev_high, "PREVIOUS_DAY"

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_high = get_1030_candle_high(broker, symbol, access_token, today_str)
    if today_high is not None:
        print(f"[ALGO] {symbol}: వెనకటి రోజు డేటా లేదు, ఈరోజు 10:30 High = {today_high} వాడుతున్నాం.")
        return today_high, "RUNNING_DAY"

    print(f"[ERROR] {symbol}: 10:30 high ఎక్కడా దొరకలేదు — స్ట్రాటజీ మొదలుపెట్టం.")
    return None, "UNAVAILABLE"

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

def init_leg_state(symbol, entry_ref_price, source):
    return {
        "symbol": symbol,
        "status": "PENDING",
        "entry_ref_price": entry_ref_price,
        "entry_ref_source": source,
        "entry_trigger_price": round(entry_ref_price + ENTRY_BUFFER_POINTS, 2),
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
    strikes + entry reference (వెనకటి రోజు 10:30 High, ఇది ఎప్పుడైనా తెలిసేదే)
    లెక్కించి legs ని సెటప్ చేస్తుంది — దీనివల్ల 9:15 దాటిన వెంటనే entry breakout
    అవకాశం మిస్ కాకుండా ఉంటుంది (బటన్ మళ్ళీ నొక్కాల్సిన అవసరం ఉండదు).
    Returns True అయితే legs రెడీ, False అయితే abort అయ్యింది (state["is_active"]=False).
    """
    broker = session["broker"]
    access_token = session["access_token"]

    print(f"[ALGO] [{phone}] 9:15 candle కోసం wait చేస్తోంది (broker చార్ట్ ప్రకారం పూర్తయ్యేదాకా)...")
    high_915 = low_915 = None

    while state["is_active"]:
        now_str = datetime.now().strftime("%H:%M")
        high_915, low_915 = fetch_915_high_low(broker, access_token)
        if high_915 is not None and low_915 is not None:
            break

        if now_str >= DATA_WAIT_CUTOFF_TIME:
            with state_lock:
                state["is_active"] = False
                state["phase"] = "STOPPED"
                state["trade_history"].append({
                    "leg": "-", "event": "ABORTED",
                    "message": f"9:15 candle డేటా {DATA_WAIT_CUTOFF_TIME} వరకూ దొరకలేదు — ఆగిపోయింది.",
                    "time": now_str,
                })
            print(f"[ALGO] [{phone}] 9:15 data cutoff దాటింది, abort.")
            return False

        time.sleep(DATA_WAIT_POLL_SECONDS)

    if not state["is_active"]:
        # యూజర్ wait చేస్తున్నప్పుడే Stop నొక్కి ఉండొచ్చు
        return False

    ce_symbol, pe_symbol, ce_atm, pe_atm = calculate_atm_strikes(high_915, low_915, broker)
    ce_ref_price, ce_source = get_entry_reference_high(broker, ce_symbol, access_token)
    pe_ref_price, pe_source = get_entry_reference_high(broker, pe_symbol, access_token)

    if ce_ref_price is None or pe_ref_price is None:
        with state_lock:
            state["is_active"] = False
            state["phase"] = "STOPPED"
            state["trade_history"].append({
                "leg": "-", "event": "ABORTED",
                "message": "10:30 candle డేటా (CE/PE) దొరకలేదు — ఆగిపోయింది.",
                "time": datetime.now().strftime("%H:%M"),
            })
        print(f"[ALGO] [{phone}] 10:30 reference data దొరకలేదు, abort.")
        return False

    now_str = datetime.now().strftime("%H:%M")
    with state_lock:
        state["spot_915_high"] = high_915
        state["spot_915_low"] = low_915
        state["legs"]["CE"] = init_leg_state(ce_symbol, ce_ref_price, ce_source)
        state["legs"]["PE"] = init_leg_state(pe_symbol, pe_ref_price, pe_source)
        state["phase"] = "TRADING"
        state["trade_history"].append({
            "leg": "-", "event": "STRIKES_READY",
            "message": f"CE:{ce_symbol} (ATM {ce_atm}) | PE:{pe_symbol} (ATM {pe_atm})",
            "time": now_str,
        })
    print(f"[ALGO] [{phone}] Strikes ready -> CE:{ce_symbol} PE:{pe_symbol}. Entry orders వెంటనే పెడుతోంది...")
    return True


def run_strategy_loop(phone):
    print(f"[ALGO] [{phone}] Live Monitoring, Entry Detection & Trailing SL Engine Active...")
    session = user_sessions.get(phone)
    state = trading_states.get(phone)
    if not session or not state:
        print(f"[ALGO] [{phone}] session/state missing, aborting loop.")
        return

    broker = session["broker"]
    access_token, api_key = session["access_token"], session["api_key"]
    quantity = session["lots"] * session["lot_size"]

    # ---- Phase 1: 9:15 candle కోసం wait చేసి, legs సెటప్ చేయడం ----
    if not wait_for_915_data_and_setup_legs(phone, session, state):
        active_threads.pop(phone, None)
        return

    entry_orders_placed = False

    while state["is_active"]:
        now_str = datetime.now().strftime("%H:%M")

        if now_str >= SQUARE_OFF_TIME:
            print(f"[ALGO] [{phone}] 3:10 PM reached. Squaring off & cancelling orders...")
            with state_lock:
                for leg_name, leg in state["legs"].items():
                    if leg.get("status") == "ENTERED":
                        place_market_exit_order(broker, access_token, api_key, leg["symbol"], quantity)
                        leg["status"] = "TIME_EXIT"
                        state["trade_history"].append(
                            {"leg": leg_name, "event": "TIME_EXIT", "time": now_str, "symbol": leg["symbol"]})
                cancel_all_broker_orders(broker, access_token, api_key)
                state["is_active"] = False
            break

        if not entry_orders_placed:
            for leg_name, leg in state["legs"].items():
                res = place_entry_breakout_order(
                    broker, access_token, api_key, leg["symbol"], quantity, leg["entry_trigger_price"])
                order_id = (res.get("data", {}).get("order_id") if isinstance(res.get("data"), dict) else None) \
                    or res.get("order_id") or res.get("id")
                leg["entry_order_id"] = order_id
                with state_lock:
                    state["trade_history"].append(
                        {"leg": leg_name, "event": "ENTRY_ORDER_PLACED",
                         "trigger": leg["entry_trigger_price"], "time": now_str})
                print(f"[ALGO] [{phone}] {leg_name} Entry order placed @ {leg['entry_trigger_price']} -> id:{order_id}")
            entry_orders_placed = True

        for leg_name, leg in state["legs"].items():

            if leg["status"] == "PENDING" and leg["entry_order_id"]:
                st = get_order_status(broker, leg["entry_order_id"], access_token, api_key)
                if st["status"] in FILLED_STATUSES:
                    entry_price = float(st.get("avg_price") or leg["entry_trigger_price"])
                    with state_lock:
                        leg["entry_price"] = entry_price
                        leg["high_since_entry"] = entry_price
                        leg["current_sl"] = round(entry_price - INITIAL_SL_POINTS, 2)
                        leg["target_price"] = round(entry_price + TARGET_POINTS, 2)
                        leg["status"] = "ENTERED"

                    sl_res = place_sl_sell_order(broker, access_token, api_key, leg["symbol"],
                                                  quantity, leg["current_sl"])
                    sl_order_id = (sl_res.get("data", {}).get("order_id") if isinstance(sl_res.get("data"), dict) else None) \
                        or sl_res.get("order_id") or sl_res.get("id")
                    leg["sl_order_id"] = sl_order_id

                    with state_lock:
                        state["trade_history"].append(
                            {"leg": leg_name, "event": "ENTERED", "price": entry_price, "time": now_str})
                    print(f"[ALGO] [{phone}] {leg_name} ENTERED @ {entry_price} | SL:{leg['current_sl']} | Target:{leg['target_price']}")

            elif leg["status"] == "ENTERED":
                ltp = get_ltp(broker, leg["symbol"], access_token, api_key)
                if ltp is None:
                    continue

                if ltp >= leg["target_price"]:
                    print(f"[ALGO] [{phone}] {leg_name} TARGET HIT @ {ltp} -> స్ట్రాటజీ ఆగిపోతోంది")
                    with state_lock:
                        for other_name, other_leg in state["legs"].items():
                            if other_name != leg_name and other_leg.get("status") == "ENTERED":
                                place_market_exit_order(broker, access_token, api_key, other_leg["symbol"], quantity)
                                other_leg["status"] = "SQUARE_OFF_ON_TARGET"
                                state["trade_history"].append(
                                    {"leg": other_name, "event": "SQUARE_OFF_ON_TARGET", "time": now_str})

                        cancel_all_broker_orders(broker, access_token, api_key)
                        place_market_exit_order(broker, access_token, api_key, leg["symbol"], quantity)
                        leg["status"] = "TARGET_HIT"
                        state["trade_history"].append(
                            {"leg": leg_name, "event": "TARGET_HIT", "price": ltp, "time": now_str})
                        state["is_active"] = False
                    break

                if ltp > leg["high_since_entry"]:
                    with state_lock:
                        leg["high_since_entry"] = ltp
                        steps = math.floor((leg["high_since_entry"] - leg["entry_price"]) / TRAIL_STEP_POINTS)
                        new_sl = round(leg["entry_price"] - INITIAL_SL_POINTS + steps * TRAIL_SL_MOVE_POINTS, 2)
                        if new_sl > leg["current_sl"]:
                            leg["current_sl"] = new_sl
                            sl_order_id = leg.get("sl_order_id")
                        else:
                            sl_order_id = None
                    if sl_order_id:
                        modify_sl_order(broker, sl_order_id, new_sl, access_token, api_key)
                        print(f"[ALGO] [{phone}] {leg_name} SL Trailed -> {new_sl} (LTP:{ltp})")

                if ltp <= leg["current_sl"]:
                    with state_lock:
                        leg["status"] = "SL_HIT"
                        state["sl_hit_count"] += 1
                        state["trade_history"].append(
                            {"leg": leg_name, "event": "SL_HIT", "price": ltp, "time": now_str})
                    print(f"[ALGO] [{phone}] {leg_name} SL HIT @ {ltp}")

        if not state["is_active"]:
            print(f"[ALGO] [{phone}] Strategy Stopped (Target Achieved).")
            break

        time.sleep(MONITOR_POLL_SECONDS)

    active_threads.pop(phone, None)

# ==============================================================================
# 14. API ENDPOINTS — APPROVAL / ADMIN
# ==============================================================================

@app.route('/request-approval', methods=['POST', 'OPTIONS'])
def request_approval():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    data = request.json or {}
    phone = data.get("phone")
    if not phone:
        return jsonify({"status": "error"}), 400

    existing = db_get_user(phone)
    if existing and existing.get("status") == "APPROVED":
        return jsonify({"status": "success", "message": "Already approved"}), 200

    db_upsert_user(phone, "PENDING", None)
    return jsonify({"status": "success"}), 200


@app.route('/get-pending-requests', methods=['GET'])
def get_pending_requests():
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    phones = db_list_pending()
    return jsonify([{"phone": p, "time": "Just now"} for p in phones]), 200


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
        db_upsert_user(phone, "APPROVED", datetime.now().isoformat())
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

    if status != "APPROVED" or not approved_at:
        return jsonify({"status": status, "expired": False, "days_left": None}), 200

    approved_dt = datetime.fromisoformat(approved_at)
    days_passed = (datetime.now() - approved_dt).days
    days_left = SUBSCRIPTION_DAYS - days_passed
    expired = days_left <= 0

    return jsonify({
        "status": "APPROVED",
        "approved_at": approved_at,
        "days_left": max(days_left, 0),
        "expired": expired,
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
    if (datetime.now() - approved_dt).days >= SUBSCRIPTION_DAYS:
        return jsonify({"status": "error", "message": "Subscription expired"}), 403

    with state_lock:
        if trading_states.get(phone, {}).get("is_active"):
            return jsonify({"status": "error", "message": "ఇప్పటికే ఈ యూజర్ కోసం strategy running ఉంది"}), 409

    broker = data.get("broker", "upstox").lower()
    session = {
        "broker": broker,
        "access_token": data.get("access_token") or data.get("api_secret", ""),
        "api_key": data.get("api_key", ""),
        "client_id": data.get("client_id", ""),
        "lots": int(data.get("lots", 1)),
        "lot_size": int(data.get("lot_size", 10)),
    }
    user_sessions[phone] = session

    # ⬇️ ఇక్కడ synchronously 9:15/10:30 డేటా కోసం wait చేయం (request hang అవకుండా).
    # బదులుగా వెంటనే thread మొదలుపెడతాం — అది 9:15 candle పూర్తయ్యేదాకా (broker చార్ట్
    # ప్రకారం) wait చేసి, పూర్తయిన వెంటనే entry breakout ఆర్డర్లు వెంటనే పెడుతుంది.
    # ఇలా చేయడం వల్ల యూజర్ 9:10కే Start నొక్కినా ఒక్క entry అవకాశం కూడా మిస్ కాదు.
    state = new_trading_state()
    state["is_active"] = True
    trading_states[phone] = state

    strategy_thread = threading.Thread(target=run_strategy_loop, args=(phone,))
    strategy_thread.daemon = True
    strategy_thread.start()
    active_threads[phone] = strategy_thread

    return jsonify({
        "status": "success",
        "message": f"Strategy Queued for Broker: {broker.upper()}. 9:15 candle పూర్తయ్యేదాకా wait చేస్తుంది.",
        "phase": "WAITING_FOR_915_DATA",
        "target_points": TARGET_POINTS,
        "trail_step_points": TRAIL_STEP_POINTS,
        "trail_sl_move_points": TRAIL_SL_MOVE_POINTS,
        "initial_sl_points": INITIAL_SL_POINTS,
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
                    {"leg": leg_name, "event": "MANUAL_STOP", "time": datetime.now().strftime("%H:%M")})

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
        },
        "history": state["trade_history"],
    }), 200

# ==============================================================================
# 16. SERVER INITIALIZATION
# ==============================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

