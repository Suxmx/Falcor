# Plan6 Phase1 GUI Profiler Launcher Handoff

## 模块职责

把 `HybridMeshVoxel` 的批处理启动入口改成真正可用于 GUI profiler 验收的入口：用户直接通过 `run_HybridMeshVoxel.bat` 打开 Mogwai 时，既能选择 Phase1 的 execution mode，也会默认看到 profiler 窗口，而不是还要手动按 `P` 或先设环境变量。

## 当前状态

- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py` 现在会在 `apply_renderer_overrides()` 中读取 `HYBRID_OPEN_PROFILER`，默认值为 `True`；脚本运行时会直接执行 `m.profiler.enabled = True`，所以 Mogwai 打开后 profiler UI 会默认弹出。
- `E:\GraduateDesign\Falcor_Cp\run_HybridMeshVoxel.bat` 新增第 4 个可选参数 `HYBRID_EXECUTION_MODE`，当前调用格式是：
  `run_HybridMeshVoxel.bat [scene] [output_mode] [reference_view] [execution_mode]`
- batch 默认值现在是：
  - `HYBRID_OUTPUT_MODE=composite`
  - `HYBRID_REFERENCE_VIEW=near`
  - `HYBRID_EXECUTION_MODE=ByObjectRoute`
  - `HYBRID_OPEN_PROFILER=1`
- batch 启动信息也会额外打印：
  - `Execution: ...`
  - `Profiler: ...`
  方便确认当前 GUI 验收跑的是哪条 graph。

## 关键文件

- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py`
- `E:\GraduateDesign\Falcor_Cp\run_HybridMeshVoxel.bat`
- `E:\GraduateDesign\Falcor_Cp\docs\memory\2026-04-06_plan6_execution_mode_split.md`

## 验证与证据

- Python 语法检查通过：
  `python -m py_compile scripts\Voxelization_HybridMeshVoxel.py`
- 实际通过 batch 启动 Mogwai 做了 GUI smoke：
  `cmd /c run_HybridMeshVoxel.bat "E:\GraduateDesign\Falcor_Cp\Scene\Arcade\Arcade.pyscene" composite near ForceMeshPipeline`
- Mogwai 窗口截图证据在：
  `C:\Users\42450\AppData\Local\Temp\codex-window-2026-04-06_11-31-12.png`
- 这张截图里可以直接看到：
  - profiler 窗口已默认打开
  - 左侧 graph pass 列表只有 `MeshGBuffer`、`MeshStyleDirectAOPass`、`ToneMapper`
  - 因此 `run_HybridMeshVoxel.bat` 已经可以直接用于 `ForceMeshPipeline` 的 GUI profiler 验收

## 后续使用方式

- 默认 hybrid GUI 验收：
  `run_HybridMeshVoxel.bat`
- 强制 mesh 单路：
  `run_HybridMeshVoxel.bat "E:\GraduateDesign\Falcor_Cp\Scene\Arcade\Arcade.pyscene" composite near ForceMeshPipeline`
- 强制 voxel 单路：
  `run_HybridMeshVoxel.bat "E:\GraduateDesign\Falcor_Cp\Scene\Arcade\Arcade.pyscene" composite near ForceVoxelPipeline`
- 如果后续要临时关闭 profiler，再显式设：
  `set HYBRID_OPEN_PROFILER=0`
  或从外部 PowerShell 里设同名环境变量后再启动。
