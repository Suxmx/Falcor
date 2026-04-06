# Plan6 Phase2 Validation Script Handoff

## 模块职责

把 `validate_phase2_resolved_routes.py` 从“只输出 count + sample 的一次性验证脚本”补成“默认导出全部实例明细，并明确说明它会在验证完成后主动退出”的批处理验证入口。

## 当前状态

- `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\validate_phase2_resolved_routes.py` 现在在每个视角下都会额外导出：
  - `blend_infos`
  - `all_instance_infos`
- 脚本启动时会打印：
  - 当前 scene
  - 输出 JSON 路径
  - `keep_open` 状态
- 脚本结束时会打印：
  - validation finished
  - 输出文件路径
  - 是否“主动退出”还是“保持 Mogwai 继续运行”
- 新增环境变量：
  - `PHASE2_VALIDATE_KEEP_OPEN=1`
  设定后脚本不会在写完 JSON 后主动退出，适合人工继续留在 Mogwai 里看结果。

## 关键文件

- `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\validate_phase2_resolved_routes.py`
- `E:\GraduateDesign\Falcor_Cp\docs\memory\2026-04-06_plan6_phase2_validation_script.md`

## 验证

- 已实际重新运行：
  `E:\GraduateDesign\Falcor_Cp\build\windows-vs2022\bin\Release\Mogwai.exe --script E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\validate_phase2_resolved_routes.py --scene E:\GraduateDesign\Falcor_Cp\Scene\Arcade\Arcade.pyscene --width=1600 --height=900`
- 输出 JSON 已包含完整 `all_instance_infos` / `blend_infos`，见：
  `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\phase2_resolved_routes_summary.json`

## 后续继续时先看

- 这个脚本是验证脚本，不是给用户长期停留在 GUI 里调试的入口；默认退出是有意行为。
- 如果后续还要扩展 Phase3/4 的 profiler 验证，优先沿用这份脚本的“默认导出全部明细 + 可选 keep_open”模式，不要再退回成只有 sample 的 summary。
