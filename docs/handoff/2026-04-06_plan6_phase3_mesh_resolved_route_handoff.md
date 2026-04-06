# Plan6 Phase3 Mesh Resolved Route Handoff

## 模块职责

让 hybrid `ByObjectRoute` 下的 mesh 正式链改为消费 `resolved execution route`，而不是继续只看 authoring route，并保持 Phase5 debug full-source、runtime graph switch、Arcade 默认入口与 `HybridCompositePass.viewMode` 语义不回退。

## 当前状态

- `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.h`
  `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.cpp`
  新增了 `Scene::GeometryInstanceRouteFilterMode`，并把 raster draw filtering 拆成两条路径：
  - `Authoring`
  - `Resolved`
- `Scene::createDrawArgs()` / `getDrawArgs()` / `rasterize()` 现在都支持按 `Resolved` 过滤；mask 语义仍沿用原来的三个位，但解释改成：
  - `MeshOnly bit -> MeshResolved`
  - `Blend bit -> NeedsBoth`
  - `VoxelOnly bit -> VoxelResolved`
- `Scene::updateGeometryInstanceResolvedRoutes()` 现在在 resolved-route 结果变化时会清空 resolved draw-args cache，避免相机移动后继续复用旧的 mesh draw args。
- 新增 Python introspection helper：
  - `scene.get_filtered_mesh_instance_ids(instance_route_mask, use_resolved_routes=False)`
  便于直接确认 mesh 正式链实际提交了哪些 triangle-mesh instance IDs。
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\GBuffer\GBuffer\GBufferRaster.h`
  `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\GBuffer\GBuffer\GBufferRaster.cpp`
  新增 `useResolvedExecutionRoutes` 属性；只有该开关打开且当前不是 `requireFullMeshSource` 调试路径时，`MeshGBuffer` 才走 resolved-route filtering。
- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py`
  现在只在 hybrid `ByObjectRoute` 的 `MeshGBuffer` 上显式设置：
  - `instanceRouteMask = Blend|MeshOnly`
  - `useResolvedExecutionRoutes = True`
  `MeshView` / `ForceMeshPipeline` 仍走原本的全量 mesh graph，不受 Phase3 过滤影响。
- 本轮没有改动或回退以下 Phase5 debug full-source 文件：
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\HybridVoxelMesh\HybridCompositePass.cpp`
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\RayMarchingDirectAOPass.cpp`
- 本轮也没有开始 Phase4 route-aware block/cell cull；voxel 正式链仍是 authoring-route + hit-level selective execution 的旧边界。

## 验证与证据

- Python 语法检查通过：
  `python -m py_compile scripts\Voxelization_HybridMeshVoxel.py`
- 受影响目标构建通过：
  `tools\.packman\cmake\bin\cmake.exe --build build\windows-vs2022 --config Release --target GBuffer HybridVoxelMesh Voxelization Mogwai`
- Phase3 验证脚本：
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase3\validate_phase3_mesh_resolved.py`
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase3\validate_phase3_mesh_voxel_side_probe.py`
- 关键结果文件：
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase3\phase3_mesh_resolved_validation.json`
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase3\phase3_mesh_voxel_side_probe.json`
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase3\validate_phase3_mesh_resolved.stdout.log`
  - `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase3\validate_phase3_mesh_voxel_side_probe.stdout.log`
- `phase3_mesh_resolved_validation.json` 说明：
  - `near`：
    - 6 个 `Blend` 全是 `NeedsBoth`
    - `mesh_instance_ids_authoring = [0,1,2,3,4,5]`
    - `mesh_instance_ids_resolved = [0,1,2,3,4,5]`
  - `far`：
    - `Blend` resolved-route 变成 `3 x NeedsBoth + 3 x VoxelResolved`
    - `VoxelResolved` 实例是：
      - `Chair` `instance_id=3`
      - `Chair` `instance_id=4`
      - `Cabinet` `instance_id=5`
    - `mesh_instance_ids_authoring = [0,1,2,3,4,5]`
    - `mesh_instance_ids_resolved = [0,1,2]`
  - 这说明 Phase3 后 mesh 正式链已经只消费：
    - `MeshResolved`
    - `NeedsBoth`
    而 `VoxelResolved` 已从 mesh draw args 中移除。
- 同一份 JSON 的 profiler 对照里，`far` 视角下切 `MeshGBuffer.useResolvedExecutionRoutes`：
  - `MeshGBuffer.gpu mean`: `0.8701 -> 0.8427 ms`
  - `MeshStyleDirectAOPass.gpu mean`: `2.0972 -> 2.0757 ms`
  - `RayMarchingDirectAOPass.gpu mean`: `2.3460 -> 2.3219 ms`
  - 说明 mesh 正式链已出现小幅下降，但默认 Arcade `far` 里仍有 `Arch/poster` 这类 `NeedsBoth` 大物体，GPU 时间不会像整景单路 graph 那样剧烈消失。
- `phase3_mesh_voxel_side_probe.json` 额外对 `Chair/Cabinet` 做了单对象 voxel-side probe；结果再次确认目标实例处于 `VoxelResolved` 时，切换 resolved mesh filtering 后 mesh pass 指标会有下降趋势，但幅度仍受同帧剩余 `NeedsBoth` / voxel 链成本噪声影响。

## 关键文件

- `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.h`
- `E:\GraduateDesign\Falcor_Cp\Source\Falcor\Scene\Scene.cpp`
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\GBuffer\GBuffer\GBufferRaster.h`
- `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\GBuffer\GBuffer\GBufferRaster.cpp`
- `E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py`
- `E:\GraduateDesign\Falcor_Cp\build\profiling\2026-04-06_plan6_phase3\validate_phase3_mesh_resolved.py`

## 后续继续时先看

- Phase3 已经完成 mesh 正式链消费 resolved-route，不要再把 resolved-route 写回 `GeometryInstanceData.flags`。
- 如果后续要继续做 Phase4，优先看：
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\ReadVoxelPass.cpp`
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\RayMarchingDirectAOPass.cpp`
  - `E:\GraduateDesign\Falcor_Cp\Source\RenderPasses\Voxelization\RayMarchingTraversal.slang`
  当前 `RayMarchingDirectAOPass` 仍会进 route-agnostic `blockMap`，所以 voxel 正式链还不会像 mesh draw args 一样直接把 `MeshResolved` 物体裁掉。
- 如果后续验收只看 profiler 数字，很容易误判 Phase3 没生效；先用 `scene.get_filtered_mesh_instance_ids()` 对照 `resolved_route`，再看 profiler 中 `MeshGBuffer / MeshStyleDirectAOPass` 的变化。
