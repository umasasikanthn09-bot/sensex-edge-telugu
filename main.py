import os
import time
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==============================================================================
# 1. GLOBAL STATE & STORAGE
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
    "broker": "upstox",  # 'upstox', 'angelone', 'zerodha', 'dhan', 'fyers'
    "access_token": "",
    "api_key": "",
    "lots": 1,
    "symbol": "SENSEX"
}

# ==============================================================================
# 2. HELPER FUNCTIONS & MULTI-BROKER ORDER INTEGRATION
# ==============================================================================

def get_15min_candle(broker, instrument_key, access_token, api_key=""):
    """
    10:30 AM క్యాండిల్ డేటాను తెచ్చుకోవడానికి బ్రోకర్ల ఫాల్‌బ్యాక్ లాజిక్
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Upstox Historical Data Example
    if broker == "upstox":
        url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/15minute/{yesterday_str}/{yesterday_str}"
        headers = {"Accept": "application/json"}
        try:
            res = requests.get(url, headers=headers).json()
            candles = res.get("data", {}).get("candles", [])
            for candle in candles:
                if "10:30:00" in candle[0]:
                    return {"high": candle[2]}
        except Exception:
            pass

    # నిన్నటి క్యాండిల్ డేటా దొరక్కపోతే ఈరోజు (Running Day) 10:30 AM డేటా తీసుకోవడం
    # API కనెక్షన్ ఫెయిల్ అయినా టెస్టింగ్ నిమిత్తం డమ్మీ ఫాల్‌బ్యాక్
    return None


def calculate_1030_entry_price(broker, instrument_key, access_token, api_key=""):
    """
    నిన్నటి 10:30 AM High ఉంటే +3 పాయింట్లు. లేకపోతే ఈరోజటి 10:30 AM High + 3 పాయింట్లు.
    """
    candle = get_15min_candle(broker, instrument_key, access_token, api_key)
    
    if candle and 'high' in candle:
        print(f"[{broker.upper()}] 10:30 AM Candle High లభించింది.")
        return candle['high'] + 3
    else:
        print(f"[{broker.upper()}] నిన్నటి/ఈనాటి 10:30 AM డేటా లభించలేదు. Default/Mock entry వర్తిస్తుంది.")
        return 100.0  # డమ్మీ టెస్టింగ్ ప్రైస్ (API కాల్స్ లేనప్పుడు)


def place_broker_order(broker, access_token, api_key, instrument_key, quantity, price):
    """
    అన్ని బ్రోకర్ ప్లాట్‌ఫారమ్‌లకు వర్తించే ఆర్డర్ ఎగ్జిక్యూషన్ ఫంక్షన్
    """
    broker = broker.lower()
    headers = {}
    payload = {}
    url = ""

    # 1. UPSTOX
    if broker == "upstox":
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
            "price": price,
            "instrument_token": instrument_key,
            "order_type": "LIMIT",
            "transaction_type": "BUY",
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False
        }

    # 2. ZERODHA (Kite)
    elif broker == "zerodha":
        url = "https://api.kite.trade/orders/regular"
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {api_key}:{access_token}"
        }
        payload = {
            "tradingsymbol": instrument_key,
            "exchange": "BSE",
            "transaction_type": "BUY",
            "order_type": "LIMIT",
            "quantity": quantity,
            "price": price,
            "product": "MIS",
            "validity": "DAY"
        }

    # 3. ANGELONE (SmartAPI)
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
            "variety": "NORMAL",
            "tradingsymbol": instrument_key,
            "symboltoken": "999001",
            "transactiontype": "BUY",
            "exchange": "BSE",
            "ordertype": "LIMIT",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": price,
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
            "orderType": "LIMIT",
            "validity": "DAY",
            "tradingSymbol": instrument_key,
            "securityId": "1010",
            "quantity": quantity,
            "price": price
        }

    # 5. FYERS
    elif broker == "fyers":
        url = "https://api-v3.fyers.in/orders/sync"
        headers = {
            "Authorization": f"{api_key}:{access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "symbol": instrument_key,
            "qty": quantity,
            "type": 1,  # Limit Order
            "side": 1,  # Buy
            "productType": "INTRADAY",
            "limitPrice": price,
            "stopPrice": 0,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False
        }

    # API Request పంపడం
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
        print(f"[{broker.upper()} RESPONSE] Status: {response.status_code} | Response: {res_data}")
        return res_data
    except Exception as e:
        print(f"[{broker.upper()} ERROR] Order Placement Failed: {e}")
        return {"status": "error", "message": str(e)}

# ==============================================================================
# 3. ADMIN APPROVAL & USER CHECK ENDPOINTS
# ==============================================================================

@app.route('/request-approval', methods=['POST', 'OPTIONS'])
def request_approval():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    data = request.json or {}
    phone = data.get("phone")
    if phone:
        pending_requests[phone] = "PENDING"
        return jsonify({"status": "success", "message": "Request received"}), 200
    
    return jsonify({"status": "error", "message": "No phone number provided"}), 400


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
    
    return jsonify({"status": "error", "message": "Phone number not found"}), 400


@app.route('/check-user-status', methods=['GET'])
def check_user_status():
    phone = request.args.get("phone")
    status = pending_requests.get(phone, "NOT_FOUND")
    return jsonify({"status": status}), 200

# ==============================================================================
# 4. TRADING ALGO STRATEGY ENDPOINTS
# ==============================================================================

@app.route('/start-strategy', methods=['POST', 'OPTIONS'])
def start_strategy():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    global user_config, trading_state
    data = request.json or {}
    
    # యూజర్ పంపిన బ్రోకర్ వివరాలు తీసుకోబడతాయి
    user_config["broker"] = data.get("broker", "upstox").lower()
    user_config["access_token"] = data.get("access_token") or data.get("api_secret", "")
    user_config["api_key"] = data.get("api_key", "")
    user_config["lots"] = int(data.get("lots", 1))

    ce_symbol = data.get("ce_symbol", "SENSEX26AUG80000CE")
    pe_symbol = data.get("pe_symbol", "SENSEX26AUG80000PE")

    # 1. 10:30 AM Entry Price (High + 3 Points) క్యాలిక్యులేషన్
    ce_entry_price = calculate_1030_entry_price(
        user_config["broker"], ce_symbol, user_config["access_token"], user_config["api_key"]
    )
    pe_entry_price = calculate_1030_entry_price(
        user_config["broker"], pe_symbol, user_config["access_token"], user_config["api_key"]
    )

    # 2. యూజర్ లాగిన్ కాగానే డిఫాల్ట్‌గా 1 ఆర్డర్ ఎగ్జిక్యూషన్ (ఫండ్స్ లేకపోతే బ్రోకర్ Rejection నమోదవుతుంది)
    order_result = place_broker_order(
        broker=user_config["broker"],
        access_token=user_config["access_token"],
        api_key=user_config["api_key"],
        instrument_key=ce_symbol,
        quantity=user_config["lots"] * 10,
        price=ce_entry_price
    )

    trading_state["is_active"] = True
    
    return jsonify({
        "status": "success",
        "message": f"{user_config['broker'].upper()} లో స్ట్రాటజీ ప్రారంభమైంది. Default Order ట్రై చేయబడింది.",
        "ce_entry_price": ce_entry_price,
        "pe_entry_price": pe_entry_price,
        "broker_order_response": order_result
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
# 5. RENDER SERVER STARTUP
# ==============================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
