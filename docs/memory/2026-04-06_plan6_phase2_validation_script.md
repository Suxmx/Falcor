# 2026-04-06 Plan6 Phase2 Validation Script

- `build\profiling\2026-04-06_plan6_phase2\validate_phase2_resolved_routes.py` 是批处理验证脚本，不是交互式 Mogwai 入口；它写完 JSON 后会主动 `exit()`，现象是窗口过一会自己关闭，不是闪退。
- 如果后续需要让 Mogwai 在验证完成后继续停留，先设 `PHASE2_VALIDATE_KEEP_OPEN=1`；默认输出里也要直接导出全部实例明细，避免只看 sample 误解总数。
