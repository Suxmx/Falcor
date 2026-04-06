# 2026-04-06 Plan6 Execution Mode Split

- `HybridCompositePass.viewMode` 是下游显示枚举；`scripts\Voxelization_HybridMeshVoxel.py` 当前无论 `Composite / MeshOnly / VoxelOnly / RouteDebug / BlendMask` 都会固定建 mesh+voxel 正式链，不能再把它复用成 execution mode。
- 当前 voxel selective execution 只在 `RayMarchingTraversal.slang` 的 hit/cell 接受阶段生效，`AnalyzePolygon.cs.slang` 写出的 `blockMap` 仍是“任意 solid voxel 即占用”的 route-agnostic 掩码；若不补 route-aware block/cell cull，profiler 里的 `RayMarchingDirectAOPass` 不会因 `MeshOnly` 物体明显下降。
- 后续计划文档必须把 `Blend` 的执行语义写清楚：`Blend` 不是“永远双路”，而是允许在当前帧被解析成 `MeshResolved / VoxelResolved / NeedsBoth`；如果只优化显式 `MeshOnly / VoxelOnly`，结果仍不满足目标。
- 用 `Start-Process -RedirectStandardOutput` 抓 Mogwai 的 Python 脚本日志时，嵌入式 `print()` 默认可能一直缓冲到进程正常退出；如果像 Phase 1 这样只做启动期 smoke 然后手动关窗，`[HybridMeshVoxel]` 的 graph/pass 诊断会看起来“没打印出来”。规避方式是在启动前显式设置 `PYTHONUNBUFFERED=1`，再从 `build\logs\*.stdout.log` 取 graph 证据。
- Mogwai 的 profiler 窗口不需要改 `SampleApp` 或模拟键盘 `P`；Falcor Python 已暴露 `m.profiler.enabled`，在脚本里设为 `True` 就会默认弹出 profiler UI。后续如果只是想让某个脚本启动即进入可测状态，优先在 `.py` 里处理，不要额外改 C++ 或做窗口自动化。
- 如果要在 Mogwai GUI 里运行时切单路成本，但又不能破坏 `HybridCompositePass.viewMode` 的 debug full-source 语义，最小做法不是复用 `MeshOnly/VoxelOnly` 视图枚举，而是把 `ByObjectRoute`、`MeshOnly`、`VoxelOnly` 三套 graph 同时 `m.addGraph()` 进去，让用户从左上 `Graphs` 下拉切 active graph；Mogwai 只执行 active graph，所以另一条正式链会从 profiler/pass 列表里真正消失。
