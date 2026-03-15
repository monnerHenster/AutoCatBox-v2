# Changelog

## 2.0.1
- Add session aggregation for out-of-order Tuya reports.
- Require both `excretion_time_day` and `cat_weight` before webhook reporting.
- Normalize `cat_weight` to kg (scale-aware) before posting to Home Assistant webhook.
- Add idle/max window flush strategy to define message batch completion.

