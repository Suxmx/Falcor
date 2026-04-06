# Plan6 Phase4 Next AI Prompt

你现在在仓库 `E:\GraduateDesign\Falcor_Cp` 的分支 `codex/plan6-execution-mode-split` 上继续工作。

先严格遵守 `AGENTS.md`，并先阅读：
1. `docs/memory/`
2. `.FORAGENT/plan6_hybrid_execution_mode_split.md`
3. `docs/handoff/2026-04-06_plan6_phase2_blend_resolved_route_handoff.md`
4. `docs/handoff/2026-04-06_plan6_phase3_mesh_resolved_route_handoff.md`
5. `docs/handoff/2026-04-05_plan5_phase5_meshonly_debug_fix_handoff.md`

当前基线：
- Phase 1 已完成，Mogwai GUI 左上 `Graphs` 可运行时切 `ByObjectRoute / MeshOnly / VoxelOnly`。
- profiler 默认打开，不要回退。
- `Scene/Arcade/Arcade.pyscene` 默认入口不坏，不要恢复 Arcade 强制 route override。
- Phase5 debug full-source 语义不能坏。
- Phase 2 已完成：`Blend` 每帧会在 `Scene` 中解析成独立 runtime `resolved_route`。
- Phase 3 已完成：mesh 正式链已消费 `resolved execution route`；`VoxelResolved` 已从 mesh draw args / raster 中移除。
- 当前已知边界：中距离时可能先出现“mesh 被裁掉，但 voxel/composite 还没稳定接管”的空窗；这是 Phase 4 前的预期现象，不要回头撤销 Phase 3。

这次只做 plan6 Phase 4，不要提前做 Phase 5。

Phase 4 目标：
- 让 voxel 正式链从 hit-level selective execution 进入 block-level route-aware cull。
- 当对象是 `MeshResolved` 时，voxel 正式链不要再只是“进了 block 再跳过 hit”，而是尽量在 block 级别就不进入。
- 修掉当前中距离“物体先消失、再更远才出现 voxel 结果”的接管空窗，但不要通过回退 Phase 3 或删除 debug full-source 逻辑来规避。

主要修改范围：
- 新增 route-prepare pass（放在 `ReadVoxelPass` 之后、`RayMarchingDirectAOPass` 之前）
- `Source/RenderPasses/Voxelization/ReadVoxelPass.cpp`
- `Source/RenderPasses/Voxelization/RayMarchingDirectAOPass.cpp`
- `Source/RenderPasses/Voxelization/RayMarchingTraversal.slang`
- `scripts/Voxelization_HybridMeshVoxel.py`

实现要求：
- 继续保持 `GeometryInstanceRenderRoute` 是 authoring route，不要改写它。
- `HybridCompositePass.viewMode` 继续只表示 debug/view mode，不能复用成 execution mode。
- `ForceMeshPipeline / ForceVoxelPipeline` 继续只是全局强制单路 graph。
- 优先做 block-level route-aware cull，不要提前上 cell-level / cache layout 扩展。
- 低 confidence / invalid identity 体素要保守处理，不要激进强裁。
- 不要改动或回退这些文件中的 Phase5 debug full-source 逻辑：
  - `Source/RenderPasses/HybridVoxelMesh/HybridCompositePass.cpp`
  - `Source/RenderPasses/Voxelization/RayMarchingDirectAOPass.cpp`

验证要求：
- 至少构建：
  `tools\.packman\cmake\bin\cmake.exe --build build\windows-vs2022 --config Release --target GBuffer HybridVoxelMesh Voxelization Mogwai`
- 优先用 Mogwai profiler / pass 列表 / 明确测试对象验证，不要只看 FPS。
- 必须明确说明：
  - Phase 4 后 voxel 正式链为什么已经减少了 `MeshResolved` 物体的 block traversal 成本
  - 中距离“先消失再出现”是否已消失；如果没有，剩余卡点在哪
  - 为什么这一步仍然还不是 Phase 5 的 cell-level 优化

交付要求：
- 完成后补 `docs/handoff`
- 如有新坑，补 `docs/memory`
- 不要做无关重构
