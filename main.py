import time
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # HTML Frontend నుండి వచ్చె Requests ని అనుమతించడానికి

# Global State Variables (ట్రేడింగ్ స్టేట్ ని స్టోర్ చేయడానికి)
trading_state = {
    "is_active": False,
    "target_achieved": False,
    "sl_hit_count": 0,
    "active_trade": None,  # Current trade metrics (CE/PE)
    "trade_history": []
}

# User Config Credentials (Frontend నుండి సెట్ అవుతాయి)
user_config = {
    "broker": "upstox",
    "api_key": "",
    "api_secret": "",
    "lots": 2
}

# ==============================================================================
# Helper Functions (Broker Data & Calculations)
# ==============================================================================

def fetch_915_candle_levels():
    """
    1) Sensex Index 15-Min Timeframe లో 9:15 Candle Close అయిన తర్వాత
       9:15 Candle High (CE Strike) మరియు Low (PE Strike) తీసుకోవడం.
    """
    # NOTE: మీ Broker API ద్వారా Real-time 9:15 Candle levels పొందాలి.
    # ఉదాహరణకు Demo values:
    sensex_915_high = 72500  # CE Strike Price
    sensex_915_low = 72000   # PE Strike Price
    
    return round(sensex_915_high, -2), round(sensex_915_low, -2)


def fetch_prev_day_1030_high(strike_symbol):
    """
    2) Previous Day 10:30 Candle High ని Broker API నుండి పొందడం.
    """
    # NOTE: Broker historical API ని ఉపయోగించి గత రోజు 10:30 High తీసుకోవాలి.
    # ఉదాహరణకు:
    mock_prev_1030_high = 200.0  
    return mock_prev_1030_high


def place_broker_order(symbol, order_type, price, lots):
    """
    Broker API కి Order పంపే ఫంక్షన్
    """
    print(f"[{datetime.now()}] PLACING ORDER: {order_type} {symbol} at ₹{price} | Lots: {lots}")
    return {"status": "SUCCESS", "order_id": f"ORD_{int(time.time())}"}

# ==============================================================================
# Main Strategy Execution Loop
# ==============================================================================

def run_strategy_loop():
    global trading_state, user_config

    # 6) Target పూర్తయితే ఆర్డర్స్ ఎగ్జిక్యూషన్ పూర్తిగా ఆగిపోవాలి
    if trading_state["target_achieved"]:
        print("Target already achieved for today. Trading Halted.")
        return

    # 1) 9:15 Candle High & Low నుండి CE, PE Strikes ఎంపిక
    ce_strike, pe_strike = fetch_915_candle_levels()
    
    # 2) Entry Price = Previous Day 10:30 Candle High + 3 Points
    ce_prev_high = fetch_prev_day_1030_high(f"SENSEX_{ce_strike}_CE")
    pe_prev_high = fetch_prev_day_1030_high(f"SENSEX_{pe_strike}_PE")

    ce_entry_trigger = ce_prev_high + 3.0
    pe_entry_trigger = pe_prev_high + 3.0

    print(f"CE Strike: {ce_strike} | Entry Trigger: {ce_entry_trigger}")
    print(f"PE Strike: {pe_strike} | Entry Trigger: {pe_entry_trigger}")

    # ==========================================================================
    # Monitoring Market & Managing Trades
    # ==========================================================================
    
    # ఇక్కడ Live LTP (Last Traded Price) మానిటర్ చేయాలి
    current_ltp = 205.0  # (ఉదాహరణకు CE Trigger హిట్ అయిందనుకుందాం)
    current_symbol = f"SENSEX_{ce_strike}_CE"

    # ENTRY LOGIC
    if trading_state["active_trade"] is None and not trading_state["target_achieved"]:
        if current_ltp >= ce_entry_trigger:
            entry_price = current_ltp
            
            # 3) Stoploss = Entry - 15 Points
            initial_sl = entry_price - 15.0
            
            # 4) Target Exit = Entry + 100 Points
            target_price = entry_price + 100.0

            # Order Execution
            place_broker_order(current_symbol, "BUY", entry_price, user_config["lots"])

            trading_state["active_trade"] = {
                "symbol": current_symbol,
                "entry_price": entry_price,
                "current_sl": initial_sl,
                "target_price": target_price,
                "highest_price_seen": entry_price,
                "sl_trailed": False
            }

            # Trade History Update
            trading_state["trade_history"].append({
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": current_symbol,
                "type": "BUY",
                "price": entry_price,
                "status": "ENTRY EXECUTED"
            })

    # EXIT & TRAILING STOPLOSS LOGIC
    if trading_state["active_trade"] is not None:
        trade = trading_state["active_trade"]
        
        # Update highest price reached during the trade
        if current_ltp > trade["highest_price_seen"]:
            trade["highest_price_seen"] = current_ltp

        # 5) Entry నుండి 50 points పైకి వెళ్తే, Stoploss 20 points పైకి జరగాలి (Trailing SL)
        points_gained = trade["highest_price_seen"] - trade["entry_price"]
        if points_gained >= 50.0 and not trade["sl_trailed"]:
            trade["current_sl"] += 20.0
            trade["sl_trailed"] = True
            print(f"Trailing SL Triggered! New SL: {trade['current_sl']}")

        # 4) TARGET EXIT HIT (+100 Points)
        if current_ltp >= trade["target_price"]:
            place_broker_order(trade["symbol"], "SELL", current_ltp, user_config["lots"])
            
            # 6) Target Complete - ఆ తర్వాత Order Executions ఆగిపోవాలి
            trading_state["target_achieved"] = True
            trading_state["active_trade"] = None
            
            trading_state["trade_history"].append({
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": current_symbol,
                "type": "SELL (TARGET)",
                "price": current_ltp,
                "status": "TARGET HIT (+100 PTS)"
            })
            print("🎉 100 Points Target Hit! Halting further trades for today.")

        # 3) STOPLOSS EXIT HIT
        elif current_ltp <= trade["current_sl"]:
            place_broker_order(trade["symbol"], "SELL", current_ltp, user_config["lots"])
            trading_state["sl_hit_count"] += 1
            
            trading_state["trade_history"].append({
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": current_symbol,
                "type": "SELL (SL)",
                "price": current_ltp,
                "status": "SL HIT"
            })
            trading_state["active_trade"] = None
            print("⚠️ Stoploss Hit!")

# ==============================================================================
# API Endpoints for Frontend (HTML Dashboard)
# ==============================================================================

@app.route('/start-strategy', methods=['POST'])
def start_strategy():
    global user_config, trading_state
    data = request.json
    
    user_config["broker"] = data.get("broker")
    user_config["api_key"] = data.get("api_key")
    user_config["api_secret"] = data.get("api_secret")
    user_config["lots"] = data.get("lots", 2)

    trading_state["is_active"] = True
    
    # కోడ్ రన్ చేయడం ప్రారంభం
    run_strategy_loop()
    
    return jsonify({
        "status": "success",
        "message": "కనెక్ట్ అయ్యింది! Sensex 15Min Strategy ప్రారంభమైంది."
    })

@app.route('/get-history', methods=['GET'])
def get_history():
    return jsonify({
        "state": {
            "is_active": trading_state["is_active"],
            "target_achieved": trading_state["target_achieved"],
            "sl_hit_count": trading_state["sl_hit_count"]
        },
        "history": trading_state["trade_history"]
    })

import os

if __name__ == '__main__':
    # Render ఇచ్చే డైనమిక్ PORT ని తీసుకోవడం కోసం
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
