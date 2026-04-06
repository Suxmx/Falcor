# Plan6 Phase1 Execution Mode Split Handoff

## 模块职责

在不改动 Phase5 debug full-source C++ 基线的前提下，把 hybrid 入口里的 `debug/view mode` 和 `execution/perf mode` 拆开，并给 `scripts\Voxelization_HybridMeshVoxel.py` 增加可直接用于 profiler 验收的整景单路 graph。

## 当前状态

- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py` 新增独立 `HYBRID_EXECUTION_MODE` 解析，支持：
  - `ByObjectRoute`
  - `ForceMeshPipeline`
  - `ForceVoxelPipeline`
- 默认仍是 `ByObjectRoute`，所以 `Scene\Arcade\Arcade.pyscene` 默认入口不变，`ARCADE_REFERENCE_ROUTES` 仍保持空表，没有恢复任何强制 route override。
- `ByObjectRoute` 保持当前 hybrid graph 语义不变，实际 pass 顺序是：
  `MeshGBuffer -> MeshStyleDirectAOPass -> HybridBlendMaskPass -> VoxelizationPass -> ReadVoxelPass -> RayMarchingDirectAOPass -> HybridCompositePass -> ToneMapper`
- `ForceMeshPipeline` 现在只建：
  `MeshGBuffer -> MeshStyleDirectAOPass -> ToneMapper`
  不再创建 `VoxelizationPass`、`ReadVoxelPass`、`RayMarchingDirectAOPass`、`HybridBlendMaskPass`、`HybridCompositePass`。
- `ForceVoxelPipeline` 现在只建：
  `VoxelizationPass -> ReadVoxelPass -> RayMarchingDirectAOPass -> ToneMapper`
  不再创建 `MeshGBuffer`、`MeshStyleDirectAOPass`、`HybridBlendMaskPass`、`HybridCompositePass`。
- `MeshView` 仍是原来的独立 mesh debug/style graph；Phase 1 没把它改造成新的 execution mode。如果 `HYBRID_OUTPUT_MODE=MeshView` 且 `HYBRID_EXECUTION_MODE != ByObjectRoute`，脚本会直接报错，避免把 dedicated mesh view 与新的 execution mode 混在一起。
- 本轮没有改动以下 Phase5 debug full-source 逻辑文件：
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\HybridVoxelMesh\HybridCompositePass.cpp`
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\GBuffer\GBuffer\GBufferRaster.cpp`
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\RayMarchingDirectAOPass.cpp`
- 本轮也没有开始 Phase 2 的 `Blend -> resolved execution route`，不要把这次交付误读成已经做了 object-level 单侧解析。

## 优先文件

- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py`
- `E:\GraduateDesign\Falcor_Cp\.FORAGENT\plan6_hybrid_execution_mode_split.md`
- `E:\GraduateDesign\Falcor_Cp\docs\memory\2026-04-06_plan6_execution_mode_split.md`
- `E:\GraduateDesign\Falcor_Cp\docs\handoff\2026-04-05_plan5_phase5_meshonly_debug_fix_handoff.md`

## 验证与证据

- Python 语法检查通过：
  `python -m py_compile scripts\Voxelization_HybridMeshVoxel.py`
- 受影响目标构建通过：
  `tools\.packman\cmake\bin\cmake.exe --build build\windows-vs2022 --config Release --target GBuffer HybridVoxelMesh Voxelization Mogwai`
- Mogwai 启动期 smoke 已跑三种 execution mode；为了让嵌入式 Python `print()` 落到日志，启动前显式设置了 `PYTHONUNBUFFERED=1`。运行日志在：
  - `E:\GraduateDesign\Falcor_Cp\build\logs\plan6_phase1_byobjectroute.stdout.log`
  - `E:\GraduateDesign\Falcor_Cp\build\logs\plan6_phase1_forcemeshpipeline.stdout.log`
  - `E:\GraduateDesign\Falcor_Cp\build\logs\plan6_phase1_forcevoxelpipeline.stdout.log`
- 对应 stderr 日志为空，说明这轮 smoke 没出现新的脚本/插件启动错误：
  - `E:\GraduateDesign\Falcor_Cp\build\logs\plan6_phase1_byobjectroute.stderr.log`
  - `E:\GraduateDesign\Falcor_Cp\build\logs\plan6_phase1_forcemeshpipeline.stderr.log`
  - `E:\GraduateDesign\Falcor_Cp\build\logs\plan6_phase1_forcevoxelpipeline.stderr.log`
- 当前验收证据是运行时 graph/pass 列表，不是 FPS：
  - `ByObjectRoute` 日志里能看到完整 hybrid pass 链。
  - `ForceMeshPipeline` 日志里只剩 `MeshGBuffer / MeshStyleDirectAOPass / ToneMapper`。
  - `ForceVoxelPipeline` 日志里只剩 `VoxelizationPass / ReadVoxelPass / RayMarchingDirectAOPass / ToneMapper`。

## 后续继续时先看

- 下一步直接做 Phase 2：给 `Blend` 增加每帧 `resolved execution route`，不要试图在 `HybridCompositePass.viewMode` 或 `HYBRID_OUTPUT_MODE` 上叠补丁。
- `ForceMeshPipeline / ForceVoxelPipeline` 只是全局强制单路 graph，不是 `Blend` 的 resolved route；不要在这一层偷偷实现 `Blend -> resolved execution route`。
- 如果后续要做 profiler/UI 验收，优先看 pass 列表与耗时是否真的消失，不要退回成“只切显示模式、不裁正式链”的旧逻辑。
