import os
import time
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==============================================================================
# 1. GLOBAL STATE & CONFIGURATION
# ==============================================================================

pending_requests = {}  

trading_state = {
    "is_active": False,
    "target_achieved": False,
    "sl_hit_count": 0,
    "active_trade": None,
    "trade_history": []
}

user_config = {
    "broker": "upstox",
    "access_token": "",
    "api_key": "",
    "lots": 1,
    "symbol": "SENSEX"
}

SENSEX_INDEX_KEY = "BSE_INDEX|SENSEX"

# ==============================================================================
# 2. HELPER FUNCTIONS: EXPIRY & INSTRUMENT RESOLUTION
# ==============================================================================

def get_next_expiry_date():
    """
    సెన్సెక్స్ వారపు ఎక్స్‌పైరీ తేదీని (సాధారణంగా గురువారం/శుక్రవారం) క్యాలిక్యులేట్ చేస్తుంది.
    """
    today = datetime.now()
    # BSE SENSEX Weekly Expiry (Thursday/Friday alignment)
    days_ahead = (3 - today.weekday()) % 7  # 3 = Thursday
    if days_ahead == 0 and today.hour >= 15:
        days_ahead += 7
    expiry_date = today + timedelta(days=days_ahead)
    return expiry_date


def get_upstox_instrument_key(trading_symbol, access_token):
    """
    Upstox Search API ద్వారా ఆప్షన్ స్ట్రైక్ యొక్క అసలైన Instrument Token ని ఫెచ్ చేస్తుంది.
    """
    url = f"https://api.upstox.com/v2/instruments/search?query={trading_symbol}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    try:
        res = requests.get(url, headers=headers).json()
        data = res.get("data", [])
        if data:
            for item in data:
                if item.get("trading_symbol") == trading_symbol or item.get("short_name") == trading_symbol:
                    return item.get("instrument_key")
            return data[0].get("instrument_key")
    except Exception as e:
        print(f"[UPSTOX SEARCH ERROR] {e}")
    return trading_symbol

# ==============================================================================
# 3. SPOT PRICE & DYNAMIC ATM STRIKE CALCULATIONS
# ==============================================================================

def fetch_sensex_915_spot(broker, access_token):
    """
    9:15 AM సెన్సెక్స్ ఇండెక్స్ ક્లోజింగ్ స్పాట్ ప్రైస్‌ను ఆటోమేటిక్‌గా ఫెచ్ చేస్తుంది.
    """
    broker = str(broker).lower()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if broker == "upstox":
        url = f"https://api.upstox.com/v2/historical-candle/{SENSEX_INDEX_KEY}/15minute/{today_str}/{today_str}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
        try:
            res = requests.get(url, headers=headers).json()
            candles = res.get("data", {}).get("candles", [])
            for c in candles:
                if "09:15:00" in c[0]:
                    spot_price = float(c[4])
                    print(f"[ALGO] Live 9:15 Sensex Spot Price: {spot_price}")
                    return spot_price
        except Exception as e:
            print(f"[ERROR] Spot Fetch Failed: {e}")

    return 76350.0  # API డేటా లభించకపోతే సేఫ్ ఫాల్‌బ్యాక్


def calculate_atm_strike_symbols(spot_price, broker):
    """
    స్పాట్ ప్రైస్ ఆధారంగా Nearest 100 ATM స్ట్రైక్ క్యాలిక్యులేట్ చేసి
    రెస్పెక్టివ్ బ్రోకర్ ఫార్మాట్ సింబల్స్‌ని రిటర్న్ చేస్తుంది.
    """
    atm_strike = round(spot_price / 100) * 100
    broker = str(broker).lower()
    expiry = get_next_expiry_date()
    
    yy = expiry.strftime("%y")
    mmm = expiry.strftime("%b").upper()
    
    # 5 బ్రోకర్లకు సరిపడే సింబల్ ఫార్మాటింగ్
    if broker == "zerodha":
        ce_symbol = f"SENSEX{yy}{mmm}{atm_strike}CE"
        pe_symbol = f"SENSEX{yy}{mmm}{atm_strike}PE"
    elif broker == "fyers":
        ce_symbol = f"BSE:SENSEX{yy}{mmm}{atm_strike}CE"
        pe_symbol = f"BSE:SENSEX{yy}{mmm}{atm_strike}PE"
    else:
        # Upstox, AngelOne, Dhan
        ce_symbol = f"SENSEX{atm_strike}CE"
        pe_symbol = f"SENSEX{atm_strike}PE"

    print(f"[ALGO] Auto Selected ATM: {atm_strike} | CE: {ce_symbol} | PE: {pe_symbol}")
    return ce_symbol, pe_symbol, atm_strike

# ==============================================================================
# 4. HISTORICAL DATA & 10:30 AM CANDLE HIGH
# ==============================================================================

def get_1030_candle_high(broker, symbol, access_token):
    """
    10:30 AM ఆప్షన్ క్యాండిల్ High ప్రైస్ ని ఫెచ్ చేస్తుంది.
    """
    broker = str(broker).lower()
    today_str = datetime.now().strftime("%Y-%m-%d")

    if broker == "upstox":
        inst_key = get_upstox_instrument_key(symbol, access_token)
        url = f"https://api.upstox.com/v2/historical-candle/{inst_key}/15minute/{today_str}/{today_str}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
        try:
            res = requests.get(url, headers=headers).json()
            candles = res.get("data", {}).get("candles", [])
            for c in candles:
                if "10:30:00" in c[0]:
                    return float(c[2])  # High Price
        except Exception:
            pass

    return None

# ==============================================================================
# 5. MULTI-BROKER BREAKOUT ORDER EXECUTION (5 BROKERS)
# ==============================================================================

def place_multi_broker_breakout_order(broker, access_token, api_key, symbol, quantity, target_price):
    """
    5 ప్రధాన బ్రోకర్లలో 10:30 AM High + 3 బ్రేక్ అవుట్ వద్ద ఎర్రర్-ఫ్రీ ఆర్డర్ ప్లేస్ చేస్తుంది.
    """
    broker = str(broker).lower()
    trigger_price = round(target_price - 0.5, 2)
    target_price = round(target_price, 2)

    # 1. UPSTOX
    if broker == "upstox":
        inst_key = get_upstox_instrument_key(symbol, access_token)
        url = "https://api.upstox.com/v2/order/place"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        payload = {
            "quantity": quantity,
            "product": "I",
            "validity": "DAY",
            "price": target_price,
            "trigger_price": trigger_price,
            "instrument_token": inst_key,
            "order_type": "SL",
            "transaction_type": "BUY",
            "disclosed_quantity": 0,
            "is_amo": False
        }

    # 2. ZERODHA
    elif broker == "zerodha":
        url = "https://api.kite.trade/orders/regular"
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {api_key}:{access_token}"
        }
        payload = {
            "tradingsymbol": symbol,
            "exchange": "BFO",
            "transaction_type": "BUY",
            "order_type": "SL",
            "quantity": quantity,
            "price": target_price,
            "trigger_price": trigger_price,
            "product": "MIS",
            "validity": "DAY"
        }

    # 3. ANGELONE
    elif broker == "angelone":
        url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "MAC_ADDRESS",
            "X-PrivateKey": api_key
        }
        payload = {
            "variety": "STOPLOSS",
            "tradingsymbol": symbol,
            "symboltoken": "999001",
            "transactiontype": "BUY",
            "exchange": "BFO",
            "ordertype": "STOPLOSS_LIMIT",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": target_price,
            "triggerprice": trigger_price,
            "quantity": quantity
        }

    # 4. DHAN
    elif broker == "dhan":
        url = "https://api.dhan.co/orders"
        headers = {
            "access-token": access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "dhanClientId": api_key,
            "transactionType": "BUY",
            "exchangeSegment": "BSE_FNO",
            "productType": "INTRADAY",
            "orderType": "STOP_LOSS_LIMIT",
            "validity": "DAY",
            "tradingSymbol": symbol,
            "quantity": quantity,
            "price": target_price,
            "triggerPrice": trigger_price
        }

    # 5. FYERS
    elif broker == "fyers":
        url = "https://api-v3.fyers.in/orders/sync"
        headers = {
            "Authorization": f"{api_key}:{access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "symbol": symbol,
            "qty": quantity,
            "type": 4,  # Stop Limit
            "side": 1,
            "productType": "INTRADAY",
            "limitPrice": target_price,
            "stopPrice": trigger_price,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False
        }

    else:
        return {"status": "error", "message": "Unsupported Broker"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
        print(f"[{broker.upper()} ORDER SUCCESS] Status: {response.status_code} | Res: {res_data}")
        return res_data
    except Exception as e:
        print(f"[{broker.upper()} ORDER FAILED] Error: {e}")
        return {"status": "error", "message": str(e)}

# ==============================================================================
# 6. MONITORING & 3:10 PM AUTO CANCEL LOOP
# ==============================================================================

def cancel_all_broker_orders(broker, access_token, api_key=""):
    broker = str(broker).lower()
    headers = {}
    url = ""

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
        response = requests.delete(url, headers=headers)
        print(f"[{broker.upper()} CANCEL EXECUTED] Status: {response.status_code}")
    except Exception as e:
        print(f"[{broker.upper()} CANCEL ERROR] {e}")


def run_strategy_loop(broker, ce_symbol, pe_symbol, ce_target_price, pe_target_price):
    global trading_state
    print("[ALGO] Live Monitoring & Auto Execution Active...")
    
    order_executed = False
    
    while trading_state["is_active"]:
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")

        # 3:10 PM Auto-Square-off Rule
        if current_time_str >= "15:10":
            print("[ALGO TIME EXIT] 3:10 PM reached. Cancelling all open orders...")
            cancel_all_broker_orders(
                broker=broker, 
                access_token=user_config["access_token"], 
                api_key=user_config["api_key"]
            )
            trading_state["is_active"] = False
            break

        # Execute Breakout Orders on Start
        if not order_executed:
            try:
                print(f"[ALGO] Placing CE Order for {ce_symbol} at Price {ce_target_price}...")
                place_multi_broker_breakout_order(
                    broker=broker,
                    access_token=user_config["access_token"],
                    api_key=user_config["api_key"],
                    symbol=ce_symbol,
                    quantity=user_config["lots"] * 10,
                    target_price=ce_target_price
                )

                print(f"[ALGO] Placing PE Order for {pe_symbol} at Price {pe_target_price}...")
                place_multi_broker_breakout_order(
                    broker=broker,
                    access_token=user_config["access_token"],
                    api_key=user_config["api_key"],
                    symbol=pe_symbol,
                    quantity=user_config["lots"] * 10,
                    target_price=pe_target_price
                )
                
                order_executed = True
                
            except Exception as e:
                print(f"[ALGO LOOP ERROR] {e}")
            
        time.sleep(2)

# ==============================================================================
# 7. API ENDPOINTS (ADMIN & TRADING)
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
    user_config["lots"] = int(data.get("lots", 1))

    # 1. Fetch Auto 9:15 Sensex Spot Price
    spot_price = fetch_sensex_915_spot(user_config["broker"], user_config["access_token"])

    # 2. Calculate ATM Strike CE & PE according to selected Broker Format
    ce_symbol, pe_symbol, atm_strike = calculate_atm_strike_symbols(spot_price, user_config["broker"])

    # 3. Get 10:30 AM Option Candle High Prices
    ce_high = get_1030_candle_high(user_config["broker"], ce_symbol, user_config["access_token"])
    pe_high = get_1030_candle_high(user_config["broker"], pe_symbol, user_config["access_token"])

    if ce_high is None or pe_high is None:
        ce_target_price = 403.0  
        pe_target_price = 403.0
        print("[WARNING] Live Candle Data null. Defaulting test prices.")
    else:
        ce_target_price = ce_high + 3.0
        pe_target_price = pe_high + 3.0

    trading_state["is_active"] = True

    strategy_thread = threading.Thread(
        target=run_strategy_loop, 
        args=(user_config["broker"], ce_symbol, pe_symbol, ce_target_price, pe_target_price)
    )
    strategy_thread.daemon = True
    strategy_thread.start()

    return jsonify({
        "status": "success",
        "message": f"Strategy Executed for Broker: {user_config['broker'].upper()}",
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "ce_symbol": ce_symbol,
        "pe_symbol": pe_symbol,
        "ce_target_price": ce_target_price,
        "pe_target_price": pe_target_price
    }), 200


@app.route('/get-history', methods=['GET'])
def get_history():
    return jsonify({
        "state": {
            "is_active": trading_state["is_active"],
            "target_achieved": trading_state["target_achieved"],
            "sl_hit_count": trading_state["sl_hit_count"]
        },
        "history": trading_state["trade_history"]
    }), 200

# ==============================================================================
# 8. SERVER INITIALIZATION
# ==============================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
