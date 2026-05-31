import httpx
import uuid
import base64
import json
from app.xui.xuiApiRoutes import XuiApiRoutes as Routes
from config import Config


class Async3xuiApi:
    def __init__(
            self,
            username: str,
            password: str,
            ip: str,
            panel_port: str,
            web_path: str,
            subscription_port: str,
            subscription_url: str
    ):
        self.username = username
        self.password = password

        self.panel_url = (
            f"https://{ip}:{panel_port}/{web_path}".rstrip("/")
        )
        self.subscription_url = (
            f"https://{ip}:{subscription_port}/{subscription_url}".rstrip("/")
        )

        self.token: str | None = None

        self.client = httpx.AsyncClient(
            verify=False,
            timeout=30.0,
            follow_redirects=True
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    async def get_session_token(self):
        response = await self.client.post(
            f"{self.panel_url}/login",
            data={
                "username": self.username,
                "password": self.password,
                "twoFactorCode": "",
            },
        )
        response.raise_for_status()
        set_cookie = response.headers.get("set-cookie")
        if not set_cookie:
            raise RuntimeError("No Set-Cookie header from server")
        token = None
        for param in set_cookie.split(";"):
            if param.strip().startswith("3x-ui="):
                token = param.split("=", 1)[1]
                break
        if not token:
            raise RuntimeError("3x-ui cookie not found in Set-Cookie")

        self.token = token

    async def add_client_to_inbound(
            self,
            client_name: str,
            inbound_id: str):
        if self.token is None:
            raise RuntimeError(
                "Session token is not set. Call get_session_token() first."
            )

        payload = {
            "id": inbound_id,
            "settings": json.dumps({
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
                    "reset": 0,
                }]
            })
        }

        headers = {
            'Accept': 'application/json',
            'Cookie': f'3x-ui={self.token}'
        }

        response = await self.client.post(
            f"{self.panel_url}/panel/api/inbounds/addClient",
            headers=headers,
            data=payload,
        )

        response.raise_for_status()

        return response.json

    async def get_key(self, client_name: str) -> str:
        response = await self.client.get(
            f"{self.subscription_url}/{client_name}"
        )

        response.raise_for_status()

        return base64.b64decode(
            response.text
        ).decode("utf-8")


if __name__ == "__main__":
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
