from urllib.parse import urlparse, parse_qs, unquote
import json


def parse_vless(url: str):
    parsed = urlparse(url=url)

    uuid, ip_port = parsed.netloc.split("@")
    ip, port = ip_port.split(":")

    result = {
        "protocol": parsed.scheme,
        "uuid": uuid,
        "ip": ip,
        "port": port,
    }

    params = parse_qs(parsed.query)
    for k, v in params.items():
        result[k] = v[0]

    if parsed.fragment:
        result["tag"] = unquote(parsed.fragment)

    return result


def build_vless_outbound(parsed: dict) -> dict:
    """
    Превращает распаршенный VLESS в outbound Xray
    """
    outbound = {
        "tag": parsed["tag"],
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": parsed["ip"],
                    "port": int(parsed["port"]),
                    "users": [{
                        "id": parsed["uuid"],
                        "encryption": "none",
                        "flow": parsed.get("flow"),
                    }]
                }
            ]
        },
        "streamSettings": {
            "network": parsed.get("type"),
            "security": parsed.get("security"),
            "realitySettings": {
                "fingerprint": parsed.get("fp"),
                "publicKey": parsed.get("pbk"),
                "serverName": parsed.get("sni"),
                "shortId": parsed.get("sid"),
                "show": False,
                "spiderX": parsed.get("spx")
            }
        }
    }
    return outbound


def load_config(config_path: str = "config.json") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
