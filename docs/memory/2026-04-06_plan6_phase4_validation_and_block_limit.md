# 2026-04-06 Plan6 Phase4 Validation And Block Limit

- Mogwai Python `Texture.to_numpy()` 在本仓库当前环境下对 `ReadVoxelPass.blockMap` / `VoxelRoutePreparePass.routeBlockMap*` / `RayMarchingDirectAOPass.voxelInstanceID` 这类 uint 纹理会报类型转换错误，甚至让验证脚本长时间挂住；Phase4 验证应优先用 profiler、`scene.get_geometry_instance_infos()`、`scene.get_filtered_mesh_instance_ids()` 或窗口抓帧，不要再用这条读回路径。
- Phase4 的 route-aware cull 只决定“要不要进入 block”，不能表达 block 内 cell/hit 的细粒度 accepted-route；如果中距离仍出现“mesh 先退、voxel 还没稳定接管”的空窗，优先怀疑 mixed block / dominant-instance hit 级别归属，而不是回退 mesh resolved-route 或 debug full-source 逻辑。
