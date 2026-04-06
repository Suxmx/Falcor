# Plan6 Phase2 Blend Resolved Route Handoff

## 模块职责

在不改写 `GeometryInstanceRenderRoute` authoring route、不触碰 Phase5 debug full-source 三个关键 pass 的前提下，为 hybrid scene 增加独立的 runtime resolved-route 数据，把 `Blend` 从“authoring 上允许混合”细化成“当前帧落 mesh / 落 voxel / 仍需双路”。

## 当前状态

- `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.h`
  `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.cpp`
  新增了独立的 `Scene::GeometryInstanceResolvedRoute`：
  - `MeshResolved`
  - `VoxelResolved`
  - `NeedsBoth`
- `Scene` 内部现在维护：
  - `mGeometryInstanceResolvedRoutes`
  - `mGeometryInstanceResolvedRouteConfig`
  - `mGeometryInstanceResolvedRoutesDirty`
- `GeometryInstanceRenderRoute` 仍保持 authoring 语义，没有被覆写；resolved-route 是平行缓存，不写回 `GeometryInstanceData.flags`。
- `Scene::updateGeometryInstanceResolvedRoutes()` 现在会在 `Scene::update()` 里按当前帧相机/几何状态刷新 resolved-route。
- 判定规则已经固定为：
  - `MeshOnly -> MeshResolved`
  - `VoxelOnly -> VoxelResolved`
  - `Blend`：
    - `maxDistance(bounds, camera) <= blendStartDistance -> MeshResolved`
    - `minDistance(bounds, camera) >= blendEndDistance -> VoxelResolved`
    - 其他情况 -> `NeedsBoth`
- `Scene` 现在提供最小 helper / Python API：
  - `get_geometry_instance_world_bounds(instance_id)`
  - `get_geometry_instance_resolved_route(instance_id)`
  - `set_geometry_instance_resolved_route_config(blend_start_distance, blend_end_distance, enabled=True)`
  - `get_geometry_instance_info()` / `get_geometry_instance_infos()` 额外带：
    - `resolved_route`
    - `world_bounds`
    - `world_radius`
    - `camera_distance_min`
    - `camera_distance_max`
- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py` 现在不会改 authoring route；它只把当前 `HybridBlendMaskPass` 的 `blendStartDistance / blendEndDistance` 同步到 `Scene` 的 resolved-route config。
- 这份同步仍通过 `m.sceneUpdateCallback` 做，但 callback 只写 config，不直接做分类；真正分类在 `Scene::update()` 中完成，避免 callback 早于 `Scene::update()` 导致的单帧滞后。

## 关键文件

- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py`
- `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.h`
- `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.cpp`
- `E:\GraduateDesign\Falcor_Cp\docs\memory\2026-04-06_plan6_phase2_resolved_route.md`

## 验证与证据

- Python 语法检查通过：
  `python -m py_compile scripts\Voxelization_HybridMeshVoxel.py`
- 受影响目标构建通过：
  `tools\.packman\cmake\bin\cmake.exe --build build\windows-vs2022 --config Release --target GBuffer HybridVoxelMesh Voxelization Mogwai`
- Mogwai 运行验证已完成，输出在：
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\phase2_resolved_routes_summary.json`
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\validate_phase2_resolved_routes.stdout.log`
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\validate_phase2_resolved_routes.stderr.log`
- 该 summary 说明：
  - active graph 仍是 `ByObjectRoute`
  - profiler 事件里仍同时存在：
    - `MeshGBuffer`
    - `MeshStyleDirectAOPass`
    - `HybridBlendMaskPass`
    - `RayMarchingDirectAOPass`
    - `HybridCompositePass`
    - `ToneMapper`
  - 因此 Phase2 还没有让 `ByObjectRoute` 真正减少另一条正式链成本，这一点符合“只做 Phase2，不提前做 Phase3/4”的边界。
- 同一份 summary 也给出了 Arcade 默认参考视角下的 resolved-route 结果：
  - `near`: 6 个 `Blend` 实例全是 `NeedsBoth`
  - `mid`: 6 个 `Blend` 实例全是 `NeedsBoth`
  - `far`: 3 个 `NeedsBoth` + 3 个 `VoxelResolved`
  - 显式样例：
    - `Arch` (`instance_id=0`) 在参考视角下是 `NeedsBoth`
    - `Chair` (`instance_id=3`) 在 `far` 下是 `VoxelResolved`
- 为了补足 `MeshResolved` 的显式样例，另外跑了一个 Mogwai probe：
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\phase2_meshresolved_probe.json`
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\validate_phase2_meshresolved_probe.stdout.log`
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase2\validate_phase2_meshresolved_probe.stderr.log`
  - 结果显示 `Chair` (`instance_id=3`, authoring route=`Blend`)：
    - 默认 near 参考机位时：`NeedsBoth`
    - 把相机推进到该实例 bounds 附近后：`MeshResolved`
    - probe 后的 `camera_distance_max = 0.9777 < blendStartDistance(1.50)`，与判定规则一致

## 现状边界

- 这轮 **已经** 有了每帧 resolved-route 数据，也已经能在 Mogwai runtime 中随相机变化切换 `MeshResolved / VoxelResolved / NeedsBoth`。
- 这轮 **还没有** 让 `ByObjectRoute` 下的 `Blend` 物体在“整体落单侧”时减少另一条正式链成本。
- 原因不是分类没生效，而是 Phase3/4 还没开始：
  - mesh 正式链仍只消费 authoring-route mask（`Blend|MeshOnly`）
  - voxel 正式链仍只消费 authoring-route mask / hit-level route 判断（`Blend|VoxelOnly`）
  - `GBufferRaster.cpp` / `RayMarchingDirectAOPass.cpp` 本轮都没改
- 所以当前 profiler 结论必须写成：
  - `resolved-route` 数据已经 ready
  - 真实 formal cost reduction 仍依赖后续 Phase3/4 去消费这份数据

## 后续继续时先看

- 下一步只能按 plan6 继续做后续消费阶段，不要回头把 resolved-route 写回 `GeometryInstanceData.flags`。
- 如果要推进 mesh 正式链，先看：
  - `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.cpp`
  - `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.h`
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\GBuffer\GBuffer\GBufferRaster.cpp`
- 如果要推进 voxel 正式链，继续保持“不要提前做 Phase4 route-aware block/cell cull”这条边界；当前 `ReadVoxelPass / RayMarchingDirectAOPass` 只知道 authoring-route 和 hit-level selective execution。
- 不要回退以下基线：
  - `HybridCompositePass.viewMode` 只表示 debug/view mode
  - `ForceMeshPipeline / ForceVoxelPipeline` 只表示全局强制单路 graph
  - `Scene\Arcade\Arcade.pyscene` 默认入口
  - Arcade 无强制 route override
  - Phase5 debug full-source 修复
