import requests
import uuid
import json
import base64
import requests
import json
import os
import logging

# Log a simple warning message
logging.warning("This is a warning message!")


from config import Config
from fastapi import FastAPI, Query, HTTPException


app = FastAPI()


def login(username, password, vps_path):
    try:
        session = requests.Session()

        login_url = f"https://{vps_path}/login/"
        login_data = {
            'username': username,
            'password': password,
            'twoFactorCode': ''
        }

        login_resp = session.post(login_url, data=login_data, timeout=30)
        print(f"Login Status: {login_resp.status_code}")

        token = session.cookies.get('3x-ui')

        if token:
            print(f"Токен получен: {token[:50]}...")
            return token
        else:
            print("❌ Токен '3x-ui' не найден в ответе")
            print(f"🔍 Ответ сервера: {login_resp.text[:200]}")
            return None

    except requests.exceptions.SSLError as e:
        print(f"❌ SSL Error: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: проверьте адрес панели. Детали: {e}")
    except requests.exceptions.Timeout as e:
        print(f"❌ Timeout Error: сервер не ответил за 30 сек")
    except Exception as e:
        print(f"❌ Unexpected Error: {type(e).__name__}: {e}")

    return None


def add_client_inbound(
        client_name: str = "testovi",
        vps_path: str = "localhost:2053/web_path_example",
        inbound_id: str = "1",
        token: str = "token"):
    url = f"https://{vps_path}/panel/api/inbounds/addClient"

    client_settings = {
        "clients": [{
            "id": f"{str(uuid.uuid4())}",
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

    response = requests.post(
        url,
        headers=headers,
        data=payload,
        timeout=30
    )

    if response.status_code == 200:
        return response
    else:
        raise Exception(
            f"Failed to add client inbound: {response.status_code} - {response.text}")


def get_key(
        client_name: str = "testovi",
        sub_path: str = "localhost:123/sub"):
    url = f"https://{sub_path}/{client_name}"
    print(url)
    response = requests.get(url)

    config_data = response.text
    decoded_data = base64.b64decode(config_data).decode('utf-8')

    return decoded_data


def parse_vless(key:str):
    key = key.replace("vless://", "").split("?")
    uuid, ip = key[0].split("@")
    ip, port = ip.split(":")
    data = key[1].split("&")
    parsed = {item.split('=')[0]: item.split('=')[1] for item in data}
    parsed["uuid"] = uuid
    parsed["ip"] = ip
    parsed["port"] = port
    
    return parsed


@app.get("/create-client")
def create_client(name: str = Query(...)):
    CONFIG_PATH = "config.json"
    try:
        vps_paths = [f"{Config.VPS[i]}:{Config.PANEL_PORTS[i]}/{Config.WEB_PATHS[i]}" for i in range(len(Config.VPS))]
        sub_paths = [f"{Config.VPS[i]}:{Config.SUB_PORTS[i]}/{Config.SUB_URL}" for i in range(len(Config.VPS))]
        inbound_ids = Config.INBOUND_IDS

        username = Config.LOGIN
        password = Config.PASSWORD

        outbounds_to_add = []
        tags_to_add = []

        for i in range(len(vps_paths)):
            # 1. LOGIN
            print("login")
            token = login(username[i], password[i], vps_paths[i])
            if not token:
                raise HTTPException(status_code=500, detail=f"Login failed for VPS {i}")

            # 2. ADD CLIENT
            print("add client")
            resp = add_client_inbound(
                client_name=name,
                vps_path=vps_paths[i],
                inbound_id=inbound_ids[i],
                token=token
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Add client failed for VPS {i}")

            # 3. GET KEY
            print("get key")
            key = get_key(
                client_name=name,
                sub_path=sub_paths[i]
            )
            if not key:
                raise HTTPException(status_code=500, detail=f"Get key failed for VPS {i}")

            # 4. PARSE
            print("parse")
            parsed = parse_vless(key)

            # TAG
            tag = f"p1-server{i+1}"

            # формируем outbound
            outbound = {
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": parsed["ip"],
                            "port": int(parsed["port"]),
                            "users": [
                                {
                                    "encryption": "none",
                                    "flow": "xtls-rprx-vision",
                                    "id": parsed["uuid"]
                                }
                            ]
                        }
                    ]
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

        # === РАБОТА С ФАЙЛОМ ===
        if not os.path.exists(CONFIG_PATH):
            raise HTTPException(status_code=500, detail="config.json not found")

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        # добавляем outbounds
        if "outbounds" not in config:
            config["outbounds"] = []

        config["outbounds"].extend(outbounds_to_add)

        # добавляем теги в балансировщик
        if "routing" not in config:
            raise HTTPException(status_code=500, detail="routing not found in config")

        if "balancers" not in config["routing"] or not isinstance(config["routing"]["balancers"], list):
            raise HTTPException(status_code=500, detail="routing.balancers not found or invalid")

        balancers = config["routing"]["balancers"]

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