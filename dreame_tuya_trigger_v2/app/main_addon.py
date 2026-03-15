#!/usr/bin/env python3
"""
HA add-on 入口：从 /data/options.json 加载配置到环境变量，再运行涂鸦消费者。
"""
import json
import os

OPTIONS_PATH = "/data/options.json"


def load_options_into_env() -> None:
    if not os.path.exists(OPTIONS_PATH):
        return
    with open(OPTIONS_PATH, encoding="utf-8") as f:
        o = json.load(f)
    os.environ["TUYA_ACCESS_ID"] = str(o.get("tuya_access_id", ""))
    os.environ["TUYA_ACCESS_KEY"] = str(o.get("tuya_access_key", ""))
    os.environ["TUYA_MQ_ENV"] = str(o.get("tuya_mq_env", "event-test"))
    os.environ["HA_BASE_URL"] = str(o.get("ha_url", "")).rstrip("/")
    os.environ["HA_TOKEN"] = str(o.get("ha_token", ""))
    os.environ["VACUUM_ENTITY_ID"] = str(o.get("vacuum_entity_id", ""))
    seg = o.get("segments") or [13]
    os.environ["VACUUM_SEGMENTS"] = ",".join(str(x) for x in seg)
    os.environ["TRIGGER_CODE"] = str(o.get("trigger_code", "excretion_time_day"))
    os.environ["ENABLE_VACUUM_CALL"] = str(o.get("enable_vacuum_call", True)).lower()
    os.environ["ENABLE_WEIGHT_SAVE"] = str(o.get("enable_weight_save", True)).lower()
    os.environ["WEBHOOK_PATH"] = str(o.get("webhook_path", ""))


if __name__ == "__main__":
    load_options_into_env()
    from consumer import main
    exit(main())
