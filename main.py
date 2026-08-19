from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_CREDENTIALS = {}
TRADE_HISTORY = []
ENGINE_STATE = {"status": "Waiting for Login", "sl_hit_count": 0}

class StrategyPayload(BaseModel):
    broker: str
    api_key: str
    api_secret: str
    lots: int

@app.get("/")
def read_root():
    return {"status": "Online", "message": "SENSEX Edge Engine Active"}

# 5 BROKER LOGIN HANDLER
@app.post("/start-strategy")
def start_strategy(payload: StrategyPayload):
    USER_CREDENTIALS["broker"] = payload.broker
    USER_CREDENTIALS["api_key"] = payload.api_key
    USER_CREDENTIALS["api_secret"] = payload.api_secret
    USER_CREDENTIALS["lots"] = payload.lots

    broker = payload.broker.lower()

    # Direct Connection Brokers (AngelOne, Dhan)
    if broker in ["angelone", "dhan"]:
        USER_CREDENTIALS["access_token"] = payload.api_secret
        ENGINE_STATE["status"] = f"Active & Connected ({payload.broker.capitalize()})"
        return {"status": "Success", "message": f"{payload.broker.capitalize()} తో విజయవంతంగా కనెక్ట్ అయ్యింది!"}

    # Redirect OAuth Brokers (Upstox, Zerodha, Fyers)
    elif broker in ["upstox", "zerodha", "fyers"]:
        ENGINE_STATE["status"] = f"Pending Login ({payload.broker.capitalize()})"
        return {
            "status": "Redirect",
            "auth_url": f"https://sensex-edge-telugu-backend.onrender.com/login/{broker}?api_key={payload.api_key}"
        }
    
    return {"status": "Error", "message": "Invalid Broker Selected"}

# UPSTOX AUTH
@app.get("/login/upstox")
def login_upstox(api_key: str):
    redirect_uri = "https://sensex-edge-telugu-backend.onrender.com/callback/upstox"
    url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"
    return RedirectResponse(url=url)

@app.get("/callback/upstox")
def upstox_callback(code: str):
    api_key = USER_CREDENTIALS.get("api_key")
    api_secret = USER_CREDENTIALS.get("api_secret")
    redirect_uri = "https://sensex-edge-telugu-backend.onrender.com/callback/upstox"

    url = 'https://api.upstox.com/v2/login/authorization/token'
    headers = {'accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'code': code, 'client_id': api_key, 'client_secret': api_secret, 'redirect_uri': redirect_uri, 'grant_type': 'authorization_code'}

    res = requests.post(url, headers=headers, data=data).json()
    if "access_token" in res:
        USER_CREDENTIALS["access_token"] = res["access_token"]
        ENGINE_STATE["status"] = "Active & Running"
        return RedirectResponse(url="https://sensex-edge-telugu.onrender.com?status=success")
    return {"status": "Failed", "details": res}

@app.get("/get-history")
def get_history():
    return {"state": ENGINE_STATE, "history": TRADE_HISTORY}
