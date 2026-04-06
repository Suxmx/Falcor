# Plan6 Phase4 Voxel Route Prepare Handoff

## 模块职责

让 hybrid `ByObjectRoute` 下的 voxel 正式链从“route-agnostic blockMap + hit-level selective accept”升级为“resolved-route aware block-level cull + hit-level resolved-route accept”，同时保持：

- `GeometryInstanceRenderRoute` 继续只是 authoring route
- `HybridCompositePass.viewMode` 继续只是 debug/view mode
- `ForceMeshPipeline` / `ForceVoxelPipeline` 继续只是整景单路 graph
- Phase5 debug full-source 语义不回退

## 当前状态

- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\ReadVoxelPass.cpp`
  新增 `solidVoxelBlockData` 输出；cache 读回后会为每个 solid voxel 记录 `(linearBlockIndex, blockZ)`，供后续 route-prepare pass 直接按 block 写 route-aware occupancy。
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\VoxelRoutePreparePass.h`
  `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\VoxelRoutePreparePass.cpp`
  `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\VoxelRoutePrepare.cs.slang`
  新增 `VoxelRoutePreparePass`，每帧从 `Scene::getGeometryInstanceResolvedRoute()` 上传 resolved-route buffer，并输出：
  - `routeBlockMapMesh`
  - `routeBlockMapVoxel`
  规则仍是 Phase4 设计边界：
  - `MeshResolved` 只写 mesh map
  - `VoxelResolved` 只写 voxel map
  - `NeedsBoth` 双写
  - invalid / low-confidence identity 保守双写
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\RayMarchingDirectAOPass.cpp`
  `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\RayMarchingTraversal.slang`
  voxel 正式链现在会：
  - 在 block 级先选 `routeBlockMapMesh` / `routeBlockMapVoxel`
  - 在 hit 级继续按 `resolvedRouteBuffer + resolvedRouteConfidenceThreshold` 决定 accept
  - `requireFullVoxelSource` 触发时自动退回全 route mask + 原始 `blockMap`
- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py`
  hybrid graph 已串成：
  `ReadVoxelPass -> VoxelRoutePreparePass -> RayMarchingDirectAOPass`
  只有 hybrid `ByObjectRoute` 开启 `useResolvedExecutionRoutes=True`；`ForceVoxelPipeline` 不受这套 selective execution 影响。
- 本轮把 resolved-route confidence 默认阈值从 `0.75` 提高到 `0.95`，避免 Phase4 block cull 对 Blend authoring 物体过早做激进单侧裁剪。

## 验证与证据

- Python 语法检查通过：
  - `python -m py_compile scripts\Voxelization_HybridMeshVoxel.py`
  - `python -m py_compile build\profiling\2026-04-06_plan6_phase4\validate_phase4_voxel_route_prepare.py`
- 受影响目标构建通过：
  `tools\.packman\cmake\bin\cmake.exe --build build\windows-vs2022 --config Release --target GBuffer HybridVoxelMesh Voxelization Mogwai`
- Phase4 profiler 验证脚本：
  `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase4\validate_phase4_voxel_route_prepare.py`
  当前版本不再读回 uint 纹理，单次运行约 43 秒并会主动退出。
- 结果文件：
  `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase4\phase4_voxel_route_prepare_validation.json`

## 关键结果

- Mesh probe：
  - 目标是 `Chair instance_id=4`
  - 在 `offset_z=0.15` 时已进入 `MeshResolved`
  - `RayMarchingDirectAOPass gpu mean` 从 `1.9531 ms -> 1.9316 ms`
  - `VoxelRoutePreparePass gpu mean` 约 `0.0102 ms -> 0.0101 ms`
  这说明 Phase4 后 voxel 正式链已经开始在 block 级跳过一部分 `MeshResolved` 物体，不再完全依赖“进了 block 再在 hit 级 reject”。
- Voxel probe：
  - 目标是 `Cabinet instance_id=5`
  - 在 `offset_z=3.75` 时从 `NeedsBoth` 进入 `VoxelResolved`
  - 同一视角下 `mesh_instance_ids_resolved = [0, 1, 2, 4]`，说明 `instance_id=5` 已不再进入 mesh resolved 正式链
  - `RayMarchingDirectAOPass gpu mean` 从 `2.8630 ms -> 3.6775 ms`
  这组数据表明在 takeover 视角下，voxel 正式链会更积极地保留 route-accepted block；提高默认阈值后，Phase4 更偏向保守接管，而不是追求最激进的 block 剪裁。

## 已知边界

- 用户手测在本轮默认阈值调高前，仍观察到“离远后还有一段物体会先消失”的区间；本轮把默认阈值提高到 `0.95` 是为了缩短这段空窗，但 Phase4 仍然不能从结构上保证彻底消失。
- 原因是 Phase4 仍然只做到 block-level route-aware cull。只要 block 内还存在 mixed route / dominant-instance 归属抖动，voxel 正式链依旧只能在 hit 级决定 accept，不能像 Phase5 那样给每个 solid voxel/cell 直接携带 accepted-route mask。
- 所以如果后续继续观察到“先消失再出现”，剩余卡点应优先归到：
  - block 内 cell/hit 级 route 粒度仍不够
  - dominant-instance identity 在接管边界附近仍有抖动
  而不是回退 Phase3 mesh resolved-route 或删除 Phase5 debug full-source 逻辑。

## 为什么这一步还不是 Phase5

- Phase4 只新增了 `routeBlockMapMesh` / `routeBlockMapVoxel` 这类 block 级资源，并在 traversal 入口先决定“深不深入这个 block”。
- Phase5 需要的是 per-solid-voxel / per-cell 的 accepted-route 信息，必要时还要评估 cache layout 扩展；那一层优化解决的是 block 已经放行之后，block 内哪些 voxel 命中仍该被拒绝的问题。
- 也就是说，Phase4 解决的是 traversal 入口成本，Phase5 解决的是 block 内部 route 粒度与 takeover 稳定性。

## 关键文件

- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\ReadVoxelPass.cpp`
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\VoxelRoutePreparePass.h`
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\VoxelRoutePreparePass.cpp`
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\VoxelRoutePrepare.cs.slang`
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\RayMarchingDirectAOPass.cpp`
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\RayMarchingTraversal.slang`
- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py`
- `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase4\validate_phase4_voxel_route_prepare.py`

## 后续继续时先看

- 先复核 `phase4_voxel_route_prepare_validation.json` 里的 mesh probe / voxel probe profiler 数据，不要只看 FPS。
- 如果要继续压缩 takeover 空窗，优先进入 Phase5 的 cell-level accepted-route 设计；不要再把 block-level route map 扩展成更复杂的 debug 旁路。
- 如果还要做可视化验证，优先用窗口抓帧或 profiler + scene introspection；不要再用 uint 纹理 `to_numpy()` 读回。
