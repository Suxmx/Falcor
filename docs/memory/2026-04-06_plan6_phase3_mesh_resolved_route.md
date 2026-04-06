# 2026-04-06 Plan6 Phase3 Mesh Resolved Route

- Phase3 把 mesh 正式链切到 resolved-route 后，`Arcade` 默认 `far` 视角里 `VoxelResolved` 的 `Chair/Cabinet` 已经会从 mesh draw args 消失，但 `MeshGBuffer` GPU 时间只会小幅下降；触发条件是画面里仍有 `Arch/poster` 这类 `NeedsBoth` 大物体继续主导 raster 成本，所以验收不能只盯一条 profiler 数值。
- 这轮最稳的验收口径是同时看 `Scene.get_filtered_mesh_instance_ids(instance_route_mask, use_resolved_routes)` 和 profiler：如果 `VoxelResolved` 实例 ID 还出现在 resolved 列表里，说明 mesh selective execution 还没真正进入 draw args；如果只看 `RayMarchingDirectAOPass`，会被 Phase4 前的 route-agnostic block traversal 噪声误导。
