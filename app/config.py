from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    VPS = os.getenv("VPS").split(" ")
    SUB_URL = os.getenv("SUB_URL")
    LOGIN = os.getenv("LOGIN").split(" ")
    PASSWORD = os.getenv("PASSWORD").split(" ")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMINS = os.getenv("ADMINS").split(" ")
    INBOUND_IDS = os.getenv("INBOUND_IDS").split(" ")
    WEB_PATHS = os.getenv("WEB_PATHS").split(" ")
    SUB_PORTS = os.getenv("SUB_PORTS").split(" ")
    PANEL_PORTS = os.getenv("PANEL_PORTS").split(" ")
