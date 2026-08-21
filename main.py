import os
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # CORS Error రాకుండా అనుమతిస్తుంది

# ==============================================================================
# 1. GLOBAL STATE & STORAGE
# ==============================================================================

# User Approval Storage: {"7729903172": "PENDING"}
pending_requests = {}  

# Trading State Variables
trading_state = {
    "is_active": False,
    "target_achieved": False,
    "sl_hit_count": 0,
    "active_trade": None,
    "trade_history": []
}

user_config = {
    "broker": "upstox",
    "api_key": "",
    "api_secret": "",
    "lots": 2
}

# ==============================================================================
# 2. HELPER FUNCTIONS (10:30 AM CANDLE LOGIC)
# ==============================================================================

def get_15min_candle_from_broker(strike_type, date_obj):
    """
    ఇక్కడ మీ బ్రోకర్ (Upstox/Zerodha) API నుండి 10:30 AM క్యాండిల్ తెచ్చుకునే కోడ్ ఉంటుంది.
    డేటా లభిస్తే dictionary రూపంలో ఇస్తుంది, లేదంటే None ఇస్తుంది.
    """
    # EXAMPLE API CALL:
    # candle = broker_api.get_historical_data(strike_type, date_obj, time="10:30")
    # return candle
    return None  # ప్రస్తుతం API కనెక్షన్ లేకపోతే testing కోసం


def calculate_1030_entry_price(strike_type):
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # 1. మొదట నిన్నటి (Previous Day) 10:30 AM క్యాండిల్ కోసం వెతకడం
    candle = get_15min_candle_from_broker(strike_type, yesterday)

    # 2. నిన్నటి క్యాండిల్ లభించకపోతే, ఈరోజు (Same Day) 10:30 AM క్యాండిల్ తీసుకోవడం
    if candle is None:
        candle = get_15min_candle_from_broker(strike_type, today)
        print(f"[{strike_type}] నిన్నటి 10:30 AM క్యాండిల్ లేదు -> ఈరోజు 10:30 AM క్యాండిల్ తీసుకున్నాం.")
    else:
        print(f"[{strike_type}] నిన్నటి 10:30 AM క్యాండిల్ దొరికింది.")

    # 3. క్యాండిల్ High + 3 Points యాడ్ చేసి ఎంట్రీ ప్రైస్ లెక్కించడం
    if candle and 'high' in candle:
        high_price = candle['high']
        entry_price = high_price + 3
        return entry_price
    
    return None

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
        print(f"[APPROVAL] New request received from Phone: {phone}")
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
        print(f"[ADMIN] Phone {phone} has been {pending_requests[phone]}")
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
    
    user_config["broker"] = data.get("broker")
    user_config["api_key"] = data.get("api_key")
    user_config["api_secret"] = data.get("api_secret")
    user_config["lots"] = data.get("lots", 2)

    # -------------------------------------------------------------
    # CE & PE 10:30 AM ENTRY PRICES CALCULATION (కొత్తగా చేర్చిన లాజిక్)
    # -------------------------------------------------------------
    ce_entry_price = calculate_1030_entry_price("CE")
    pe_entry_price = calculate_1030_entry_price("PE")

    print(f"[ALGO] CE Calculated Entry Price: {ce_entry_price}")
    print(f"[ALGO] PE Calculated Entry Price: {pe_entry_price}")

    trading_state["is_active"] = True
    
    return jsonify({
        "status": "success",
        "message": "కనెక్ట్ అయ్యింది! Sensex 15Min Strategy ప్రారంభమైంది.",
        "ce_entry_price": ce_entry_price,
        "pe_entry_price": pe_entry_price
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
