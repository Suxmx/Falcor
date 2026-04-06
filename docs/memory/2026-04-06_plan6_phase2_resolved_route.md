# 2026-04-06 Plan6 Phase2 Resolved Route

- Mogwai 的 `sceneUpdateCallback` 发生在 `Scene::update()` 之前；Phase2 如果直接在 callback 里按当前相机位置做 resolved-route 分类，会天然慢一帧。规避方式是 callback 只同步 `blendStart/blendEnd` 配置，把真正的分类放进 `Scene::update()`。
- Phase2 只把 `Blend -> MeshResolved / VoxelResolved / NeedsBoth` 的 runtime 数据落到 `Scene`；在 `GBufferRaster` 和 `RayMarchingDirectAOPass` 还没消费这份数据前，`ByObjectRoute` profiler 里 mesh/voxel 正式链都会继续存在，不能把这轮当成真实降成本闭环。
