import uuid
import json
import base64
import os
import logging
import httpx
import asyncio

from config import Config
from fastapi import FastAPI, Query, HTTPException

app = FastAPI()

logging.warning("This is a warning message!")


# ---------------- LOGIN ----------------
async def login(username, password, vps_path):
    try:
        async with httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True) as client:
            login_url = f"https://{vps_path}/login/"
            login_data = {
                'username': username,
                'password': password,
                'twoFactorCode': ''
            }

            login_resp = await client.post(login_url, data=login_data)
            print(f"Login Status: {login_resp.status_code}")

            # ✅ FIX HERE
            token = login_resp.cookies.get('3x-ui')

            if token:
                print(f"Токен получен: {token[:50]}...")
                return token
            else:
                print("❌ Токен '3x-ui' не найден")
                print(f"🔍 Headers: {login_resp.headers}")
                print(f"🔍 Body: {login_resp.text[:200]}")
                return None

    except Exception as e:
        print(f"❌ Login error: {e}")

    return None


# ---------------- ADD CLIENT ----------------
async def add_client_inbound(
        client_name: str,
        vps_path: str,
        inbound_id: str,
        token: str):

    url = f"https://{vps_path}/panel/api/inbounds/addClient"

    client_settings = {
        "clients": [{
            "id": str(uuid.uuid4()),
            "flow": "xtls-rprx-vision",
            "email": client_name,
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True,
            "tgId": "",
            "subId": client_name,
            "comment": "",
            "reset": 0
        }]
    }

    payload = {
        'id': inbound_id,
        'settings': json.dumps(client_settings, ensure_ascii=False)
    }

    headers = {
        'Accept': 'application/json',
        'Cookie': f'3x-ui={token}'
    }

    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        response = await client.post(url, headers=headers, data=payload)

    if response.status_code == 200:
        return response
    else:
        raise Exception(
            f"Failed to add client inbound: {response.status_code} - {response.text}"
        )


# ---------------- GET KEY ----------------
async def get_key(client_name: str, sub_path: str):
    url = f"https://{sub_path}/{client_name}"
    print(url)

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(url)

    config_data = response.text
    decoded_data = base64.b64decode(config_data).decode('utf-8')

    return decoded_data


# ---------------- PARSE ----------------
def parse_vless(key: str):
    key = key.replace("vless://", "").split("?")
    uuid_, ip = key[0].split("@")
    ip, port = ip.split(":")
    data = key[1].split("&")
    parsed = {item.split('=')[0]: item.split('=')[1] for item in data}

    parsed["uuid"] = uuid_
    parsed["ip"] = ip
    parsed["port"] = port

    return parsed


# ---------------- MAIN ENDPOINT ----------------
@app.get("/create-client-5hJG-3Vv7-6jfv-j374")
async def create_client(name: str = Query(...)):
    CONFIG_PATH = "config.json"

    try:
        vps_paths = [
            f"{Config.VPS[i]}:{Config.PANEL_PORTS[i]}/{Config.WEB_PATHS[i]}"
            for i in range(len(Config.VPS))
        ]

        sub_paths = [
            f"{Config.VPS[i]}:{Config.SUB_PORTS[i]}/{Config.SUB_URL}"
            for i in range(len(Config.VPS))
        ]

        inbound_ids = Config.INBOUND_IDS
        username = Config.LOGIN
        password = Config.PASSWORD

        outbounds_to_add = []
        tags_to_add = []

        for i in range(len(vps_paths)):
            print("login")
            token = await login(username[i], password[i], vps_paths[i])
            if not token:
                raise HTTPException(status_code=500, detail=f"Login failed for VPS {i}")

            print("add client")
            resp = await add_client_inbound(
                client_name=name,
                vps_path=vps_paths[i],
                inbound_id=inbound_ids[i],
                token=token
            )

            if resp.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Add client failed for VPS {i}")

            print("get key")
            key = await get_key(name, sub_paths[i])
            if not key:
                raise HTTPException(status_code=500, detail=f"Get key failed for VPS {i}")

            print("parse")
            parsed = parse_vless(key)

            tag = f"p1-server{i+1}"

            outbound = {
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": parsed["ip"],
                        "port": int(parsed["port"]),
                        "users": [{
                            "encryption": "none",
                            "flow": "xtls-rprx-vision",
                            "id": parsed["uuid"]
                        }]
                    }]
                },
                "streamSettings": {
                    "network": "tcp",
                    "realitySettings": {
                        "fingerprint": parsed.get("fp", "chrome"),
                        "publicKey": parsed.get("pbk", ""),
                        "serverName": parsed.get("sni", ""),
                        "shortId": parsed.get("sid", ""),
                        "show": False,
                        "spiderX": "/"
                    },
                    "security": "reality"
                },
                "tag": tag
            }

            outbounds_to_add.append(outbound)
            tags_to_add.append(tag)

        # -------- FILE (sync, same logic) --------
        if not os.path.exists(CONFIG_PATH):
            raise HTTPException(status_code=500, detail="config.json not found")

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        if "outbounds" not in config:
            config["outbounds"] = []

        config["outbounds"].extend(outbounds_to_add)

        if "routing" not in config:
            raise HTTPException(status_code=500, detail="routing not found in config")

        balancers = config["routing"].get("balancers")
        if not isinstance(balancers, list):
            raise HTTPException(status_code=500, detail="routing.balancers not found or invalid")

        for balancer in balancers:
            if not isinstance(balancer, dict):
                continue

            if "selector" not in balancer or not isinstance(balancer["selector"], list):
                balancer["selector"] = []

            for tag in tags_to_add:
                if tag not in balancer["selector"]:
                    balancer["selector"].append(tag)

        return config

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))