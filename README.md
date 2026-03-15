# AutoCatBox Add-on Repository

Home Assistant add-on repository for cat-litter related Tuya triggers.

## Install Repository
Add this repository URL in HA add-on store:

`https://github.com/monnerHenster/AutoCatBox`

## Available Add-ons

1. `dreame_tuya_trigger` (legacy)
- Original behavior: trigger Dreame segment clean when Tuya reports `code=excretion_time_day`.

2. `dreame_tuya_trigger_v2` (test)
- New behavior with split toggles:
  - `enable_vacuum_call`: whether to trigger robot vacuum
  - `enable_weight_save`: whether to forward payload to HA webhook for weight saving
- Recommended test defaults:
  - `enable_vacuum_call: false`
  - `enable_weight_save: true`
  - `webhook_path: /api/webhook/cat_weight_from_tuya_trigger`

## Repository Layout
- `repository.yaml`
- `README.md`
- `dreame_tuya_trigger/`
- `dreame_tuya_trigger_v2/`

## Security
- Do not commit HA long-lived tokens, credentials, or backup archives to this repository.
