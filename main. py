from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import datetime
import time

app = FastAPI(title="SENSEX Edge Algo Engine")

class StrategyParams(BaseModel):
    broker: str
    api_key: str
    api_secret: str
    lots: int

execution_state = {
    "active": False,
    "sl_hit_count": 0,
    "current_position": None
}

def sensex_strategy_engine(broker: str, api_key: str, api_secret: str, lots: int):
    print(f"[{datetime.datetime.now()}] {broker.upper()} పై ఆటో స్ట్రాటజీ ప్రారంభమైంది...")
    
    # 1. 15 Min Sensex Index 9:15 Candle High & Low గెట్ చేయడం
    # 2. High కి తగ్గ CE Strike, Low కి తగ్గ PE Strike సిస్టమ్ ఆటోమేటిక్ గా ఎంచుకుంటుంది.
    
    # 3. నిన్నటి రోజటి 1:15 PM నుండి 1:45 PM మధ్య గల 15 min candles (13:15, 13:30) రేంజ్ (Range = High - Low)
    prev_day_range = 45.0  # ఉదాహరణ కిరణం క్యాలిక్యులేషన్

    # Today 9:15 Candle Low
    today_915_low = 210.0
    today_915_high = 255.0

    # Entry point & Target Calculation
    entry_level = today_915_low - prev_day_range  # Rule 3
    target_level = today_915_high + prev_day_range # Rule 6
    stoploss_points = 30.0

    print(f"Calculated Entry Level: {entry_level}, Target Level: {target_level}")

    # Monitoring Loop
    while execution_state["active"]:
        time.sleep(2) # Live Candle Stream
        
        # Simulated Live Candle Data
        current_candle_close = 165.0
        is_green_candle = True # Green Candle Check (Rule 4)
        
        # Rule 4 & 3: Entry Execution on Green Candle
        if execution_state["current_position"] is None:
            if current_candle_close <= entry_level and is_green_candle:
                print(f"[*] BUY ORDER Executed at {current_candle_close} | Lots: {lots}")
                execution_state["current_position"] = {
                    "entry_price": current_candle_close,
                    "sl": current_candle_close - stoploss_points,
                    "target": target_level,
                    "trailed": False
                }

        # Position Management
        pos = execution_state["current_position"]
        if pos:
            current_price = 198.0 # Live Option Price
            
            # Rule 7: Target దిశగా 35 పాయింట్లు వెళ్తే SL ని Entry Place లోకి మార్చడం
            if not pos["trailed"] and (current_price - pos["entry_price"]) >= 35.0:
                pos["sl"] = pos["entry_price"] # Cost to Cost SL
                pos["trailed"] = True
                print("[*] SL Trailed to Entry Price (Cost-to-Cost)")

            # Check SL Hit
            if current_price <= pos["sl"]:
                print("[!] Stoploss Hit!")
                execution_state["sl_hit_count"] += 1
                execution_state["current_position"] = None
                
                # Rule 5: 1 time SL hit అయితే ఏ కాండిల్ టచ్ అయిందో దాని 50% లెవెల్ లో Re-entry కోసం వెయిటింగ్
                if execution_state["sl_hit_count"] == 1:
                    print("[!] Waiting for 50% Candle Re-entry level...")
                    # Re-entry triggers when price hits 50% candle zone
                    
            # Check Target Hit
            elif current_price >= pos["target"]:
                print("[+] Target Hit! Exiting Trade.")
                execution_state["current_position"] = None
                break

@app.post("/start-strategy")
def start_strategy(params: StrategyParams, background_tasks: BackgroundTasks):
    execution_state["active"] = True
    background_tasks.add_task(
        sensex_strategy_engine, 
        params.broker, 
        params.api_key, 
        params.api_secret, 
        params.lots
    )
    return {"status": "started", "message": f"{params.broker.upper()} లో ఆటోమ్యాటిక్ స్ట్రాటజీ రన్ అవుతోంది."}
