"""
================================================================================
SENSEX OPTIONS AUTO-TRADING ALGO BOT
================================================================================
STRATEGY (మీ requirement ప్రకారం):
  1. 9:15 AM (15-min) SENSEX INDEX candle -> High = CE ATM strike, Low = PE ATM strike
  2. Entry reference = వెనకటి రోజు (previous trading day) 10:30 AM candle High.
     అది దొరకకపోతే -> running day (today) 10:30 AM candle High వాడతాం.
  3. Entry trigger = reference High + 3 points (breakout SL-BUY order)
  4. Entry అయిన వెంటనే SL = Entry - 15 points (ఇనీషియల్ SL)
  5. ఆ తర్వాత Trailing: ప్రతి 30 points price పైకి వెళ్ళితే, SL 15 points పైకి జరుగుతుంది
  6. Target = Entry + 100 points. Target హిట్ అయితే -> ఆ position (మరియు రెండో leg ఇంకా
     open గా ఉంటే దాన్ని కూడా) స్క్వేర్-ఆఫ్ చేసి, స్ట్రాటజీ/యాప్ మానిటరింగ్ పూర్తిగా ఆగిపోతుంది.
  7. Target హిట్ కాకపోతే -> 3:10 PM కి అన్ని open positions/pending orders ఆటోమేటిక్‌గా square-off/cancel

SUPPORTED BROKERS: Upstox, Zerodha, AngelOne, Dhan, Fyers

⚠️ ముఖ్యమైన గమనికలు (దయచేసి production లో పెట్టే ముందు తప్పకుండా చదవండి):
  - ఇది REAL MONEY తో REAL ఆర్డర్లు పెట్టే కోడ్. Live capital పెట్టే ముందు
    తప్పనిసరిగా paper-trading / sandbox / చిన్న quantity తో thorough టెస్టింగ్ చేయండి.
  - AngelOne కి "symboltoken", Dhan కి "securityId" అవసరం — ఇవి ఆయా బ్రోకర్ల
    instrument/scrip master ఫైల్ నుండి రిజాల్వ్ చేయాలి. క్రింద placeholder
    "999001" / securityId resolver పెట్టాను — వీటిని మీరు actual instrument
    master mapping తో replace చేయాలి, లేకపోతే ఆర్డర్లు REJECT అవుతాయి.
  - SENSEX index (9:15 candle) మరియు historical option-candle డేటా ఈ కోడ్‌లో
    Upstox APIకి మాత్రమే పూర్తిగా verify చేసి పెట్టాను. వేరే బ్రోకర్‌ని ఎంచుకుంటే,
    ఆ బ్రోకర్ index/historical-candle endpoint ఇంకా add చేయాల్సి ఉంటుంది
    (function లో TODO కామెంట్ పెట్టాను).
  - బ్రోకర్ APIలు తరచుగా మారుతూ ఉంటాయి — వాడే ముందు ఆయా బ్రోకర్ల అధికారిక
    docs తో endpoint/payload ఫీల్డ్‌లను verify చేసుకోండి.
  - lot_size (SENSEX contract lot size) సరిగ్గా సెట్ చేయండి — ఇది expiry batch
    బట్టి మారొచ్చు, /start-strategy request లో పంపొచ్చు (default 10 పెట్టాను).
================================================================================
"""

import os
import math
import time
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

TARGET_POINTS = 100            # Entry నుండి +100 points target
TRAIL_STEP_POINTS = 30         # ప్రతి 30 points ముందుకు వెళ్ళితే...
TRAIL_SL_MOVE_POINTS = 15      # ...SL 15 points పైకి జరుగుతుంది
INITIAL_SL_POINTS = 15         # Entry తర్వాత మొదటి SL = 15 points, ఆ తర్వాతే ట్రయిలింగ్ కండిషన్ వర్తిస్తుంది
ENTRY_BUFFER_POINTS = 3        # Reference High + 3 = Entry trigger (బ్రేక్‌అవుట్)
MONITOR_POLL_SECONDS = 2
SQUARE_OFF_TIME = "15:10"      # 3:10 PM auto square-off

SENSEX_INDEX_KEY_UPSTOX = "BSE_INDEX|SENSEX"

# Live డేటా రాకపోతే వాడే సేఫ్టీ ఫాల్‌బ్యాక్ విలువలు
FALLBACK_915_HIGH = 76500.0
FALLBACK_915_LOW = 76200.0
FALLBACK_1030_HIGH = 400.0

# ==============================================================================
# 2. GLOBAL STATE & CONFIGURATION
# ==============================================================================

pending_requests = {}

trading_state = {
    "is_active": False,
    "sl_hit_count": 0,
    "trade_history": [],
    "legs": {"CE": {}, "PE": {}},
}

user_config = {
    "broker": "upstox",
    "access_token": "",
    "api_key": "",       # Zerodha api_key / AngelOne X-PrivateKey / Dhan client-id / Fyers app_id
    "client_id": "",     # అవసరమైతే extra client identifiers కోసం
    "lots": 1,
    "lot_size": 10,      # SENSEX lot size — expiry batch బట్టి మారొచ్చు, నిర్ధారించుకోండి
}

# ==============================================================================
# 3. EXPIRY & INSTRUMENT RESOLUTION
# ==============================================================================

def get_next_expiry_date():
    """సెన్సెక్స్ వారపు ఎక్స్‌పైరీ తేదీని (గురువారం ఆధారంగా) క్యాలిక్యులేట్ చేస్తుంది."""
    today = datetime.now()
    days_ahead = (3 - today.weekday()) % 7  # 3 = Thursday
    if days_ahead == 0 and today.hour >= 15:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def get_upstox_instrument_key(trading_symbol, access_token):
    """Upstox Search API ద్వారా ఆప్షన్ స్ట్రైక్ యొక్క instrument_key తెస్తుంది."""
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


def resolve_angelone_symboltoken(symbol):
    """
    ⚠️ TODO: AngelOne scrip-master (https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json)
    నుండి actual symboltoken ఇక్కడ resolve చేయాలి. ప్రస్తుతానికి placeholder.
    """
    return "999001"


def resolve_dhan_security_id(symbol):
    """
    ⚠️ TODO: Dhan instrument master CSV (https://images.dhan.co/api-data/api-scrip-master.csv)
    నుండి actual securityId ఇక్కడ resolve చేయాలి. ప్రస్తుతానికి placeholder.
    """
    return None

# ==============================================================================
# 4. 9:15 AM CANDLE (INDEX) -> ATM STRIKE SELECTION
# ==============================================================================

def fetch_915_high_low(broker, access_token):
    """
    9:15 AM (15-min) SENSEX INDEX క్యాండిల్ High & Low తెస్తుంది.
    High -> CE ATM strike reference, Low -> PE ATM strike reference.
    ప్రస్తుతం Upstox index-historical API మాత్రమే ఇంప్లిమెంట్ చేయబడింది.
    """
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
        # TODO: ఈ బ్రోకర్ కోసం index historical-candle endpoint add చేయాలి
        print(f"[WARNING] {broker} కోసం 9:15 index-candle API ఇంకా ఇంప్లిమెంట్ కాలేదు.")

    print("[WARNING] 9:15 candle live data దొరకలేదు, fallback విలువలు వాడుతున్నాం.")
    return FALLBACK_915_HIGH, FALLBACK_915_LOW


def calculate_atm_strikes(high_915, low_915, broker):
    """High (9:15) ఆధారంగా CE ATM, Low (9:15) ఆధారంగా PE ATM స్ట్రైక్‌లను లెక్కిస్తుంది."""
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
        # Upstox, AngelOne, Dhan
        ce_symbol, pe_symbol = f"SENSEX{ce_atm}CE", f"SENSEX{pe_atm}PE"

    print(f"[ALGO] CE ATM:{ce_atm} ({ce_symbol}) | PE ATM:{pe_atm} ({pe_symbol})")
    return ce_symbol, pe_symbol, ce_atm, pe_atm

# ==============================================================================
# 5. 10:30 AM CANDLE (PREVIOUS DAY -> FALLBACK RUNNING DAY)
# ==============================================================================

def get_1030_candle_high(broker, symbol, access_token, target_date):
    """target_date (YYYY-MM-DD) రోజు ఆప్షన్ యొక్క 10:30 AM 15-min క్యాండిల్ High."""
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
        # TODO: ఈ బ్రోకర్ కోసం historical-candle endpoint add చేయాలి
        print(f"[WARNING] {broker} కోసం 10:30 candle API ఇంకా ఇంప్లిమెంట్ కాలేదు.")
    return None


def get_entry_reference_high(broker, symbol, access_token):
    """
    ముందుగా వెనకటి రోజు (previous trading day) 10:30 High చూస్తుంది.
    అది దొరకకపోతే running day (today) 10:30 High వాడుతుంది.
    రెండూ దొరకకపోతే fallback.
    Returns: (reference_price, source) — source: PREVIOUS_DAY / RUNNING_DAY / FALLBACK
    """
    prev_day = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_high = get_1030_candle_high(broker, symbol, access_token, prev_day)
    if prev_high is not None:
        print(f"[ALGO] {symbol}: వెనకటి రోజు ({prev_day}) 10:30 High = {prev_high} వాడుతున్నాం.")
        return prev_high, "PREVIOUS_DAY"

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_high = get_1030_candle_high(broker, symbol, access_token, today_str)
    if today_high is not None:
        print(f"[ALGO] {symbol}: వెనకటి రోజు డేటా లేదు, ఈరోజు ({today_str}) 10:30 High = {today_high} వాడుతున్నాం.")
        return today_high, "RUNNING_DAY"

    print(f"[WARNING] {symbol}: 10:30 high ఎక్కడా దొరకలేదు, fallback వాడుతున్నాం.")
    return FALLBACK_1030_HIGH, "FALLBACK"

# ==============================================================================
# 6. LIVE LTP FETCH (5 BROKERS) — Trailing SL మానిటరింగ్ కోసం
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
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/getLtpData"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "Accept": "application/json", "X-PrivateKey": api_key}
            payload = {"exchange": "BFO", "tradingsymbol": symbol,
                       "symboltoken": resolve_angelone_symboltoken(symbol)}
            res = requests.post(url, json=payload, headers=headers, timeout=5).json()
            return float(res.get("data", {}).get("ltp"))

        elif broker == "dhan":
            sec_id = resolve_dhan_security_id(symbol)
            if not sec_id:
                print("[DHAN LTP ERROR] securityId resolve కాలేదు — resolve_dhan_security_id() పూర్తి చేయాలి")
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
# 7. ORDER PLACEMENT — ENTRY (BREAKOUT SL-BUY) — 5 బ్రోకర్లు
# ==============================================================================

def place_entry_breakout_order(broker, access_token, api_key, symbol, quantity, entry_trigger_price):
    """Reference High + 3 వద్ద బ్రేక్‌అవుట్ SL-BUY ఎంట్రీ ఆర్డర్ పెడుతుంది."""
    broker = str(broker).lower()
    trigger_price = round(entry_trigger_price, 2)
    limit_price = round(trigger_price + 0.5, 2)  # slippage buffer తో buy limit

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
        url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                   "Accept": "application/json", "X-UserType": "USER", "X-SourceID": "WEB",
                   "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "127.0.0.1",
                   "X-MACAddress": "MAC_ADDRESS", "X-PrivateKey": api_key}
        payload = {"variety": "STOPLOSS", "tradingsymbol": symbol,
                   "symboltoken": resolve_angelone_symboltoken(symbol), "transactiontype": "BUY",
                   "exchange": "BFO", "ordertype": "STOPLOSS_LIMIT", "producttype": "INTRADAY",
                   "duration": "DAY", "price": limit_price, "triggerprice": trigger_price,
                   "quantity": quantity}

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
# 8. ORDER PLACEMENT — SL (SELL) ORDER — Entry అయిన తర్వాత పెట్టేది, Trailing లో modify అవుతుంది
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
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "Accept": "application/json", "X-PrivateKey": api_key}
            payload = {"variety": "STOPLOSS", "tradingsymbol": symbol,
                       "symboltoken": resolve_angelone_symboltoken(symbol), "transactiontype": "SELL",
                       "exchange": "BFO", "ordertype": "STOPLOSS_LIMIT", "producttype": "INTRADAY",
                       "duration": "DAY", "price": limit_price, "triggerprice": trigger_price,
                       "quantity": quantity}

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
    """Trailing SL అమలు — ఇప్పటికే పెట్టిన SL ఆర్డర్ trigger price ని పైకి జరుపుతుంది."""
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
# 9. ORDER STATUS CHECK (ఎంట్రీ ఫిల్ అయ్యిందా లేదా చూడటానికి)
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
# 10. TARGET EXIT (MARKET SELL) & CANCEL-ALL (3:10 PM)
# ==============================================================================

def place_market_exit_order(broker, access_token, api_key, symbol, quantity):
    """Target హిట్ / Time-exit అయినప్పుడు position ని మార్కెట్‌లో close చేయడానికి."""
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
            url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                       "Accept": "application/json", "X-PrivateKey": api_key}
            payload = {"variety": "NORMAL", "tradingsymbol": symbol,
                       "symboltoken": resolve_angelone_symboltoken(symbol), "transactiontype": "SELL",
                       "exchange": "BFO", "ordertype": "MARKET", "producttype": "INTRADAY",
                       "duration": "DAY", "quantity": quantity}

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
# 11. STRATEGY MONITORING LOOP — ENTRY + TRAILING SL + TARGET + TIME EXIT
# ==============================================================================

def init_leg_state(symbol, entry_ref_price, source):
    return {
        "symbol": symbol,
        "status": "PENDING",           # PENDING -> ENTERED -> TARGET_HIT / SL_HIT / TIME_EXIT
        "entry_ref_price": entry_ref_price,
        "entry_ref_source": source,     # PREVIOUS_DAY / RUNNING_DAY / FALLBACK
        "entry_trigger_price": round(entry_ref_price + ENTRY_BUFFER_POINTS, 2),
        "entry_order_id": None,
        "entry_price": None,
        "sl_order_id": None,
        "current_sl": None,
        "target_price": None,
        "high_since_entry": None,
    }


def run_strategy_loop(broker):
    global trading_state
    print("[ALGO] Live Monitoring, Entry Detection & Trailing SL Engine Active...")
    access_token, api_key = user_config["access_token"], user_config["api_key"]
    quantity = user_config["lots"] * user_config["lot_size"]

    entry_orders_placed = False

    while trading_state["is_active"]:
        now_str = datetime.now().strftime("%H:%M")

        # ---- 3:10 PM Auto Square-off ----
        if now_str >= SQUARE_OFF_TIME:
            print("[ALGO TIME EXIT] 3:10 PM reached. Squaring off positions & cancelling orders...")
            for leg_name, leg in trading_state["legs"].items():
                if leg.get("status") == "ENTERED":
                    place_market_exit_order(broker, access_token, api_key, leg["symbol"], quantity)
                    leg["status"] = "TIME_EXIT"
                    trading_state["trade_history"].append(
                        {"leg": leg_name, "event": "TIME_EXIT", "time": now_str, "symbol": leg["symbol"]})
            cancel_all_broker_orders(broker, access_token, api_key)
            trading_state["is_active"] = False
            break

        # ---- Entry (Breakout SL-BUY) ఆర్డర్లు ఒక్కసారే పెట్టడం ----
        if not entry_orders_placed:
            for leg_name, leg in trading_state["legs"].items():
                res = place_entry_breakout_order(
                    broker, access_token, api_key, leg["symbol"], quantity, leg["entry_trigger_price"])
                order_id = (res.get("data", {}).get("order_id") if isinstance(res.get("data"), dict) else None) \
                    or res.get("order_id") or res.get("id")
                leg["entry_order_id"] = order_id
                print(f"[ALGO] {leg_name} Entry order placed @ {leg['entry_trigger_price']} -> id:{order_id}")
            entry_orders_placed = True

        # ---- ప్రతి leg ని మానిటర్ చేయడం ----
        for leg_name, leg in trading_state["legs"].items():

            if leg["status"] == "PENDING" and leg["entry_order_id"]:
                st = get_order_status(broker, leg["entry_order_id"], access_token, api_key)
                if st["status"] in FILLED_STATUSES:
                    entry_price = float(st.get("avg_price") or leg["entry_trigger_price"])
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

                    trading_state["trade_history"].append(
                        {"leg": leg_name, "event": "ENTERED", "price": entry_price, "time": now_str})
                    print(f"[ALGO] {leg_name} ENTERED @ {entry_price} | Initial SL:{leg['current_sl']} | Target:{leg['target_price']}")

            elif leg["status"] == "ENTERED":
                ltp = get_ltp(broker, leg["symbol"], access_token, api_key)
                if ltp is None:
                    continue

                # ---- Target Hit -> ఆ leg exit + రెండో leg కూడా square-off + యాప్ పూర్తిగా STOP ----
                if ltp >= leg["target_price"]:
                    print(f"[ALGO] {leg_name} TARGET HIT @ {ltp} -> స్ట్రాటజీ ఆగిపోతోంది (App Stop)")

                    # ఇంకా open గా ఉన్న రెండో leg ని కూడా స్క్వేర్-ఆఫ్ చేస్తాం
                    for other_name, other_leg in trading_state["legs"].items():
                        if other_name != leg_name and other_leg.get("status") == "ENTERED":
                            place_market_exit_order(broker, access_token, api_key, other_leg["symbol"], quantity)
                            other_leg["status"] = "SQUARE_OFF_ON_TARGET"
                            trading_state["trade_history"].append(
                                {"leg": other_name, "event": "SQUARE_OFF_ON_TARGET", "time": now_str})

                    cancel_all_broker_orders(broker, access_token, api_key)  # పెండింగ్ Entry/SL ఆర్డర్లు అన్నీ cancel
                    place_market_exit_order(broker, access_token, api_key, leg["symbol"], quantity)
                    leg["status"] = "TARGET_HIT"
                    trading_state["trade_history"].append(
                        {"leg": leg_name, "event": "TARGET_HIT", "price": ltp, "time": now_str})

                    trading_state["is_active"] = False   # ⬅️ యాప్/స్ట్రాటజీ పూర్తిగా ఆగిపోతుంది
                    break

                # ---- Trailing SL: ప్రతి 30 points పైకి -> SL 15 points పైకి ----
                if ltp > leg["high_since_entry"]:
                    leg["high_since_entry"] = ltp
                    steps = math.floor((leg["high_since_entry"] - leg["entry_price"]) / TRAIL_STEP_POINTS)
                    new_sl = round(leg["entry_price"] - INITIAL_SL_POINTS + steps * TRAIL_SL_MOVE_POINTS, 2)
                    if new_sl > leg["current_sl"]:
                        leg["current_sl"] = new_sl
                        if leg.get("sl_order_id"):
                            modify_sl_order(broker, leg["sl_order_id"], new_sl, access_token, api_key)
                        print(f"[ALGO] {leg_name} SL Trailed -> {new_sl} (LTP:{ltp})")

                # ---- SL Hit (safety-net; బ్రోకర్ SL ఆర్డర్ కూడా ఇదే పని real-time లో చేస్తుంది) ----
                if ltp <= leg["current_sl"]:
                    leg["status"] = "SL_HIT"
                    trading_state["sl_hit_count"] += 1
                    trading_state["trade_history"].append(
                        {"leg": leg_name, "event": "SL_HIT", "price": ltp, "time": now_str})
                    print(f"[ALGO] {leg_name} SL HIT @ {ltp}")

        # Target Hit అయినప్పుడు లూప్ లోపలే is_active=False చేసాం -> ఇక్కడ వెంటనే యాప్ ఆగిపోతుంది
        if not trading_state["is_active"]:
            print("[ALGO] Strategy Stopped (Target Achieved).")
            break

        time.sleep(MONITOR_POLL_SECONDS)

# ==============================================================================
# 12. API ENDPOINTS
# ==============================================================================

@app.route('/request-approval', methods=['POST', 'OPTIONS'])
def request_approval():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    data = request.json or {}
    phone = data.get("phone")
    if phone:
        pending_requests[phone] = "PENDING"
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400


@app.route('/get-pending-requests', methods=['GET'])
def get_pending_requests():
    req_list = [{"phone": k, "time": "Just now"} for k, v in pending_requests.items() if v == "PENDING"]
    return jsonify(req_list), 200


@app.route('/admin-action', methods=['POST', 'OPTIONS'])
def admin_action():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    data = request.json or {}
    phone = data.get("phone")
    action = data.get("action")
    if phone in pending_requests:
        pending_requests[phone] = "APPROVED" if action == "APPROVE" else "REJECTED"
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400


@app.route('/check-user-status', methods=['GET'])
def check_user_status():
    phone = request.args.get("phone")
    status = pending_requests.get(phone, "NOT_FOUND")
    return jsonify({"status": status}), 200


@app.route('/start-strategy', methods=['POST', 'OPTIONS'])
def start_strategy():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    global user_config, trading_state
    data = request.json or {}

    user_config["broker"] = data.get("broker", "upstox").lower()
    user_config["access_token"] = data.get("access_token") or data.get("api_secret", "")
    user_config["api_key"] = data.get("api_key", "")
    user_config["client_id"] = data.get("client_id", "")
    user_config["lots"] = int(data.get("lots", 1))
    user_config["lot_size"] = int(data.get("lot_size", 10))

    broker, access_token = user_config["broker"], user_config["access_token"]

    # 1. 9:15 AM SENSEX Index Candle -> High/Low
    high_915, low_915 = fetch_915_high_low(broker, access_token)

    # 2. ATM Strikes: High -> CE, Low -> PE
    ce_symbol, pe_symbol, ce_atm, pe_atm = calculate_atm_strikes(high_915, low_915, broker)

    # 3. Entry Reference: Previous day 10:30 High -> fallback Running day 10:30 High
    ce_ref_price, ce_source = get_entry_reference_high(broker, ce_symbol, access_token)
    pe_ref_price, pe_source = get_entry_reference_high(broker, pe_symbol, access_token)

    # 4. Leg State Setup
    trading_state["legs"]["CE"] = init_leg_state(ce_symbol, ce_ref_price, ce_source)
    trading_state["legs"]["PE"] = init_leg_state(pe_symbol, pe_ref_price, pe_source)
    trading_state["is_active"] = True
    trading_state["sl_hit_count"] = 0
    trading_state["trade_history"] = []

    strategy_thread = threading.Thread(target=run_strategy_loop, args=(broker,))
    strategy_thread.daemon = True
    strategy_thread.start()

    return jsonify({
        "status": "success",
        "message": f"Strategy Started for Broker: {broker.upper()}",
        "spot_915_high": high_915,
        "spot_915_low": low_915,
        "ce_symbol": ce_symbol, "ce_atm_strike": ce_atm,
        "ce_entry_trigger": trading_state["legs"]["CE"]["entry_trigger_price"],
        "ce_reference_source": ce_source,
        "pe_symbol": pe_symbol, "pe_atm_strike": pe_atm,
        "pe_entry_trigger": trading_state["legs"]["PE"]["entry_trigger_price"],
        "pe_reference_source": pe_source,
        "target_points": TARGET_POINTS,
        "trail_step_points": TRAIL_STEP_POINTS,
        "trail_sl_move_points": TRAIL_SL_MOVE_POINTS,
        "initial_sl_points": INITIAL_SL_POINTS,
    }), 200


@app.route('/stop-strategy', methods=['POST', 'OPTIONS'])
def stop_strategy():
    """Frontend 'Stop & Secure Logout' బటన్ దీన్ని కాల్ చేస్తుంది — pending ఆర్డర్లు cancel చేసి, లూప్ ఆపేస్తుంది."""
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    global trading_state
    was_active = trading_state["is_active"]
    trading_state["is_active"] = False  # run_strategy_loop తదుపరి ఇటరేషన్‌లో ఆగిపోతుంది

    if was_active:
        cancel_all_broker_orders(user_config["broker"], user_config["access_token"], user_config["api_key"])
        quantity = user_config["lots"] * user_config["lot_size"]
        for leg_name, leg in trading_state["legs"].items():
            if leg.get("status") == "ENTERED":
                place_market_exit_order(user_config["broker"], user_config["access_token"],
                                         user_config["api_key"], leg["symbol"], quantity)
                leg["status"] = "MANUAL_STOP"
                trading_state["trade_history"].append(
                    {"leg": leg_name, "event": "MANUAL_STOP", "time": datetime.now().strftime("%H:%M")})

    return jsonify({"status": "success", "message": "Strategy stopped & orders cancelled."}), 200


@app.route('/get-history', methods=['GET'])
def get_history():
    return jsonify({
        "state": {
            "is_active": trading_state["is_active"],
            "sl_hit_count": trading_state["sl_hit_count"],
            "legs": trading_state["legs"],
        },
        "history": trading_state["trade_history"],
    }), 200

# ==============================================================================
# 13. SERVER INITIALIZATION
# ==============================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

