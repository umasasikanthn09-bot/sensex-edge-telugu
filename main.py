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
    "broker": "upstox",
    "access_token": "",  # Login నాటి సజీవ Token
    "lots": 1,
    "symbol": "SENSEX"
}

# ==============================================================================
# 2. HELPER FUNCTIONS & UPSTOX INTEGRATION
# ==============================================================================

def get_15min_candle_from_upstox(instrument_key, date_str):
    """
    Upstox Historical Data API ద్వారా నిర్దిష్ట తేదీకి చెందిన 10:30 AM క్యాండిల్ వివరాలు సేకరిస్తుంది.
    """
    url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/15minute/{date_str}/{date_str}"
    headers = {"Accept": "application/json"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            candles = response.json().get("data", {}).get("candles", [])
            # 10:30 AM క్యాండిల్ ఉందో లేదో సరిచూడటం
            for candle in candles:
                # candle[0] లో timestamp ఉంటుంది (e.g., '2026-08-21T10:30:00+05:30')
                if "10:30:00" in candle[0]:
                    return {"timestamp": candle[0], "open": candle[1], "high": candle[2], "low": candle[3], "close": candle[4]}
    except Exception as e:
        print(f"[ERROR] Candle Fetching Failed: {e}")
        
    return None


def calculate_1030_entry_price(instrument_key):
    """
    అంశం 2: నిన్నటి 10:30 AM క్యాండిల్ high ఉంటే దానికి +3 పాయింట్లు.
    అది లేకపోతేనే ఈరోజటి 10:30 AM క్యాండిల్ high + 3 పాయింట్లను తీసుకుంటుంది.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 1. మొదట నిన్నటి 10:30 AM క్యాండిల్ సరిచూడటం
    candle = get_15min_candle_from_upstox(instrument_key, yesterday_str)

    # 2. నిన్నటిది లేకపోతేనే ఈరోజు 10:30 AM క్యాండిల్ వాడటం
    if candle is None:
        candle = get_15min_candle_from_upstox(instrument_key, today_str)
        print(f"[{instrument_key}] నిన్నటి 10:30 AM క్యాండిల్ లేదు -> ఈరోజు 10:30 AM క్యాండిల్ వాడుతున్నాం.")
    else:
        print(f"[{instrument_key}] నిన్నటి 10:30 AM క్యాండిల్ లభించింది.")

    if candle and 'high' in candle:
        entry_price = candle['high'] + 3
        return entry_price
    
    return None


def place_upstox_order(instrument_key, quantity, order_type="LIMIT", price=0):
    """
    అంశం 1 & 3: స్ట్రాటజీ ప్రారంభం కాగానే ఉద్దేశించిన బ్రోకర్ ఖాతాలో డిఫాల్ట్‌గా ఆర్డర్ ప్లేస్ అవుతుంది.
    ఫండ్స్ ఉంటే Executed అవుతుంది, ఫండ్స్ లేకపోతే బ్రోకర్ నుండి Rejection Order నమోదవుతుంది.
    """
    url = "https://api.upstox.com/v2/order/place"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {user_config['access_token']}"
    }
    
    payload = {
        "quantity": quantity,
        "product": "I",  # Intraday
        "validity": "DAY",
        "price": price,
        "tag": "ALGO_TRADE",
        "instrument_token": instrument_key,
        "order_type": order_type,
        "transaction_type": "BUY",
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
        print(f"[ORDER RESPONSE] Status: {response.status_code} | Data: {res_data}")
        return res_data
    except Exception as e:
        print(f"[ERROR] Order Placement Failed: {e}")
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
    
    user_config["broker"] = data.get("broker", "upstox")
    user_config["access_token"] = data.get("access_token") or data.get("api_key")  # అంశం 4: రోజూ లాగిన్ అయ్యే Access Token
    user_config["lots"] = int(data.get("lots", 1))

    # CE మరియు PE కి సంబంధించిన ఇన్‌స్ట్రుమెంట్ కీలు (ఉదాహరణకు)
    ce_instrument = data.get("ce_instrument", "NSE_FO|12345")
    pe_instrument = data.get("pe_instrument", "NSE_FO|67890")

    # 10:30 AM high క్యాలిక్యులేషన్ (+3 Points)
    ce_entry_price = calculate_1030_entry_price(ce_instrument)
    pe_entry_price = calculate_1030_entry_price(pe_instrument)

    # అంశం 3: స్ట్రాటజీ కింద లాగిన్ కాగానే డిఫాల్ట్‌గా 1 ఆర్డర్ ప్లేస్ చేయడం
    order_result = {}
    if ce_entry_price:
        # బ్రోకర్ అకౌంట్‌కి ఆర్డర్ రిక్వెస్ట్ వెళుతుంది (ఫండ్స్ లేకపోతే రిజెక్ట్ అవుతుంది)
        order_result = place_upstox_order(
            instrument_key=ce_instrument, 
            quantity=user_config["lots"] * 10, # Lot Size
            order_type="LIMIT", 
            price=ce_entry_price
        )

    trading_state["is_active"] = True
    
    return jsonify({
        "status": "success",
        "message": "Strategy Started & Default Order Sent to Broker!",
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
