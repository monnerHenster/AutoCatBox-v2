# add-on 内仅从环境变量读取（由 main_addon 从 /data/options.json 注入）
import os

PULSAR_SERVER_URL = "pulsar+ssl://mqe.tuyacn.com:7285/"
ACCESS_ID = os.environ.get("TUYA_ACCESS_ID", "")
ACCESS_KEY = os.environ.get("TUYA_ACCESS_KEY", "")
MQ_ENV = os.environ.get("TUYA_MQ_ENV", "event-test")
SUBSCRIPTION_NAME = f"{ACCESS_ID}-sub" if ACCESS_ID else ""
TRIGGER_CODE = os.environ.get("TRIGGER_CODE", "excretion_time_day")

HA_BASE_URL = os.environ.get("HA_BASE_URL", "").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
VACUUM_ENTITY_ID = os.environ.get("VACUUM_ENTITY_ID", "vacuum.s50_pro_chao_bo_shang_xia_shui_ban")
_raw = os.environ.get("VACUUM_SEGMENTS", "13")
VACUUM_SEGMENTS = [int(x) for x in _raw.split(",") if x.strip()]

ENABLE_VACUUM_CALL = os.environ.get("ENABLE_VACUUM_CALL", "true").lower() == "true"
ENABLE_WEIGHT_SAVE = os.environ.get("ENABLE_WEIGHT_SAVE", "true").lower() == "true"
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "").strip()
