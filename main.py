import os
import time
from datetime import datetime
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
# 2. ADMIN APPROVAL & USER CHECK ENDPOINTS
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
    # PENDING లో ఉన్న నంబర్లను మాత్రమే అడ్మిన్‌కు చూపిస్తుంది
    req_list = [{"phone": k, "time": "Just now"} for k, v in pending_requests.items() if v == "PENDING"]
    return jsonify(req_list), 200


@app.route('/admin-action', methods=['POST', 'OPTIONS'])
def admin_action():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    data = request.json or {}
    phone = data.get("phone")
    action = data.get("action")  # 'APPROVE' or 'REJECT'
    
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
# 3. TRADING ALGO STRATEGY ENDPOINTS
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

    trading_state["is_active"] = True
    
    return jsonify({
        "status": "success",
        "message": "కనెక్ట్ అయ్యింది! Sensex 15Min Strategy ప్రారంభమైంది."
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
# 4. RENDER SERVER STARTUP
# ==============================================================================

if __name__ == '__main__':
    # Render డైనమిక్ PORT క్యాచ్ చేయడం కోసం
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
