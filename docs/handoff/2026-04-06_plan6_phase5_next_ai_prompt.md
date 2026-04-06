# Plan6 Phase5 Next AI Prompt

你现在在仓库 `E:\GraduateDesign\Falcor_Cp` 的分支 `codex/plan6-execution-mode-split` 上继续工作。

先严格遵守 `AGENTS.md`，并先阅读：
1. `docs/memory/`
2. `.FORAGENT/plan6_hybrid_execution_mode_split.md`
3. `docs/handoff/2026-04-06_plan6_phase2_blend_resolved_route_handoff.md`
4. `docs/handoff/2026-04-06_plan6_phase3_mesh_resolved_route_handoff.md`
5. `docs/handoff/2026-04-06_plan6_phase4_voxel_route_prepare_handoff.md`
6. `docs/handoff/2026-04-05_plan5_phase5_meshonly_debug_fix_handoff.md`

当前基线：
- Phase 1/2/3/4 已完成，不要回退。
- profiler 默认打开，不要回退。
- `Scene/Arcade/Arcade.pyscene` 默认入口不坏，不要恢复 Arcade 强制 route override。
- `GeometryInstanceRenderRoute` 仍是 authoring route，不要改写。
- `HybridCompositePass.viewMode` 仍只是 debug/view mode，不能复用成 execution mode。
- `ForceMeshPipeline / ForceVoxelPipeline` 仍只是全局单路 graph。
- Phase5 debug full-source 语义不能坏，不要改坏：
  - `Source/RenderPasses/HybridVoxelMesh/HybridCompositePass.cpp`
  - `Source/RenderPasses/Voxelization/RayMarchingDirectAOPass.cpp`
- 用户已明确观察到：中距离 still 有“mesh 先退、voxel 过一段才稳定接管”的空窗；Phase4 只能缓解，不能结构性解决。
- Mogwai 验证脚本必须在 2 分钟内自动退出，不要再留下挂着的窗口。

这次只做 plan6 Phase 5，不要做无关重构。

Phase 5 目标：
- 把 voxel 正式链从 Phase4 的 block-level route-aware cull，推进到 cell / solid-voxel 级 accepted-route。
- 解决当前 takeover 边界仍存在的“先消失再出现”空窗，而不是只继续调 confidence threshold。
- 在不破坏 Phase5 debug full-source 的前提下，让 block 放行后，block 内也能稳定地按 resolved execution route 接管。

优先实现方向：
- 优先做 per-solid-voxel / per-cell accepted-route 数据，不要先碰大范围 cache layout 重构，除非证明没有更小改法。
- 如果必须扩 cache layout，旧 cache 必须明确失效并说明重生方式。
- 低 confidence / invalid identity 仍要保守处理，不要激进强裁。

优先查看文件：
- `Source/RenderPasses/Voxelization/RayMarchingTraversal.slang`
- `Source/RenderPasses/Voxelization/RayMarchingDirectAOPass.cpp`
- `Source/RenderPasses/Voxelization/ReadVoxelPass.cpp`
- `Source/RenderPasses/Voxelization/VoxelRoutePreparePass.cpp`
- `scripts/Voxelization_HybridMeshVoxel.py`
- `docs/memory/2026-04-06_plan6_phase4_validation_and_block_limit.md`

验证要求：
- 至少构建：
  `tools\.packman\cmake\bin\cmake.exe --build build\windows-vs2022 --config Release --target GBuffer HybridVoxelMesh Voxelization Mogwai`
- 优先用 Mogwai profiler、明确测试对象、窗口抓帧或 scene introspection 验证，不要只看 FPS。
- 不要再用 uint 纹理 `to_numpy()` 读回做主验证，当前环境下这条路径会报错或拖挂脚本。
- 必须明确回答：
  - 为什么 Phase 5 比 Phase 4 少掉了哪些 block 内无效 traversal / hit reject
  - 中距离“先消失再出现”是否消失；如果还没完全消失，剩余卡点是什么
  - 是否引入了新的 cache/layout 兼容成本

交付要求：
- 完成后补 `docs/handoff`
- 如有新坑，补 `docs/memory`
- 不要做无关重构
