from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    VPS = os.getenv("VPS").split(" ")
    SUB_URL = os.getenv("SUB_URL")
    LOGIN = os.getenv("LOGIN")
    PASSWORD = os.getenv("PASSWORD")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMINS = os.getenv("ADMINS").split(" ") if os.getenv("ADMINS") != None else None
    INBOUND_IDS = os.getenv("INBOUND_IDS")
    WEB_PATHS = os.getenv("WEB_PATHS")
    SUB_PORTS = os.getenv("SUB_PORTS")
    PANEL_PORTS = os.getenv("PANEL_PORTS")
