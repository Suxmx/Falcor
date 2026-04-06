# Plan6 Phase1 Runtime Graph Switch Handoff

## 模块职责

把 `HybridExecutionMode` 从“只能靠启动参数选初始 graph”推进到“打开 Mogwai 后可直接在 GUI 里切 active graph”，并保证切到 `MeshOnly` / `VoxelOnly` 时，另一条正式链不再执行，而不是只换显示结果。

## 当前状态

- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py` 现在在 hybrid 输出模式下会一次性向 Mogwai 注册三套 graph：
  - `ByObjectRoute`
  - `MeshOnly`
  - `VoxelOnly`
- 这三套 graph 的实际 pass 形态分别是：
  - `ByObjectRoute`：
    `MeshGBuffer -> MeshStyleDirectAOPass -> HybridBlendMaskPass -> VoxelizationPass -> ReadVoxelPass -> RayMarchingDirectAOPass -> HybridCompositePass -> ToneMapper`
  - `MeshOnly`：
    `MeshGBuffer -> MeshStyleDirectAOPass -> ToneMapper`
  - `VoxelOnly`：
    `VoxelizationPass -> ReadVoxelPass -> RayMarchingDirectAOPass -> ToneMapper`
- 脚本仍保留独立 `HYBRID_EXECUTION_MODE`，但它现在只负责“初始 active graph 选哪个”；运行后可以直接在 Mogwai 左上 `Graphs` 下拉里切 `ByObjectRoute / MeshOnly / VoxelOnly`，不需要重启，也不需要再改启动参数。
- 这样做的原因是要保留 `HybridCompositePass.viewMode` 的 debug full-source 语义：
  现有 `MeshOnly / VoxelOnly / RouteDebug / BlendMask` 视图仍属于 hybrid debug/view mode，不能直接重新解释成 execution mode。
- `E:\GraduateDesign\Falcor_Cp\run_HybridMeshVoxel.bat` 的启动提示已补一句：
  `GUI switch: use Mogwai Graphs dropdown to select ByObjectRoute / MeshOnly / VoxelOnly`

## 关键文件

- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py`
- `E:\GraduateDesign\Falcor_Cp\run_HybridMeshVoxel.bat`
- `E:\GraduateDesign\Falcor_Cp\docs\memory\2026-04-06_plan6_execution_mode_split.md`

## 验证与证据

- Python 语法检查通过：
  `python -m py_compile scripts\Voxelization_HybridMeshVoxel.py`
- 启动期 smoke 日志确认三套 graph 已同时注册：
  `E:\GraduateDesign\Falcor_Cp\build\logs\plan6_runtime_graph_dropdown.stdout.log`
- 该日志里可见：
  - `graph: ByObjectRoute`
  - `graph: MeshOnly`
  - `graph: VoxelOnly`
  - `runtime graphs: ByObjectRoute, MeshOnly, VoxelOnly`
  - `GUI switch: use Mogwai Graphs dropdown to select ByObjectRoute / MeshOnly / VoxelOnly`
- 结合 Mogwai 既有行为，切换 active graph 时只有当前 active graph 会被 compile/execute；因此切到 `MeshOnly` / `VoxelOnly` 后，另一条正式链会从 profiler/pass 列表里消失，而不是只是“不显示”。

## 使用方式

- 直接运行：
  `run_HybridMeshVoxel.bat`
- 进入 Mogwai 后，在左上 `Graphs` 区域的 active graph 下拉里切：
  - `ByObjectRoute`
  - `MeshOnly`
  - `VoxelOnly`
- 验收口径：
  - 切到 `MeshOnly` 后，左侧 pass 列表和 profiler 里不应再出现 `VoxelizationPass / ReadVoxelPass / RayMarchingDirectAOPass / HybridBlendMaskPass / HybridCompositePass`
  - 切到 `VoxelOnly` 后，不应再出现 `MeshGBuffer / MeshStyleDirectAOPass / HybridBlendMaskPass / HybridCompositePass`

## 后续注意

- 这次做的是 runtime graph switch，不是 `Blend -> resolved execution route`；`ByObjectRoute` 内部仍保持当前 Phase1 基线。
- 如果后续真要做到“切 `HybridCompositePass.viewMode.MeshOnly/VoxelOnly` 就自动切 execution graph”，那会触碰 debug/view 与 execution 的耦合边界，继续做前必须先重新定义 debug full-source 的保留方式。
