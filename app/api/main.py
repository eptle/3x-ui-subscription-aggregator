import json
import copy
import logging

from fastapi import FastAPI, Query, HTTPException

from config import Config
from app.xui.xuiApiInterface import Async3xuiApi
from app.utils import parse_vless, load_config, build_vless_outbound

logging.basicConfig(level=logging.INFO)
app = FastAPI()

CONFIG_PATH = "config.json"
SOLO_CONFIG_PATH = "solo_config.json"


@app.get("/create-client")
async def create_client(name: str = Query(...)):
    config = load_config(CONFIG_PATH)
    solo_config_list = list()
    base_solo_config = load_config(SOLO_CONFIG_PATH)

    outbounds = config.get("outbounds", [])
    selectors = list()

    if not (
        len(Config.VPS)
        == len(Config.LOGIN)
        == len(Config.PASSWORD)
        == len(Config.INBOUND_IDS)
        == len(Config.PANEL_PORTS)
        == len(Config.WEB_PATHS)
        == len(Config.SUB_PORTS)
    ):
        raise HTTPException(
            status_code=500,
            detail="Config arrays length mismatch"
        )

    for i, ip in enumerate(Config.VPS):
        xui = Async3xuiApi(
            username=Config.LOGIN[i],
            password=Config.PASSWORD[i],
            ip=ip,
            panel_port=Config.PANEL_PORTS[i],
            web_path=Config.WEB_PATHS[i],
            subscription_port=Config.SUB_PORTS[i],
            subscription_url=Config.SUB_URL
        )

        try:
            async with xui:
                await xui.get_session_token()
                await xui.add_client_to_inbound(
                    client_name=name,
                    inbound_id=Config.INBOUND_IDS[i]
                )
                key = await xui.get_key(name)
                parsed = parse_vless(key)
                outbound = build_vless_outbound(
                    parsed=parsed
                )
                outbounds.append(outbound)
                selectors.append(parsed.get("tag"))
                # ===== solo ===== #
                solo_config = copy.deepcopy(base_solo_config)
                solo_config["remarks"] = parsed.get("tag").split("-")[0]
                solo_config["outbounds"].append(outbound)
                solo_config_list.append(solo_config)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"VPS {ip} failed: {str(e)}"
            )

    config["outbounds"] = outbounds
    config["routing"]["balancers"][0]["selector"] = selectors

    return [config, *solo_config_list]
