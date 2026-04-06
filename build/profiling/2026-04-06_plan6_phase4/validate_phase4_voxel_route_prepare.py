import json
import os
from pathlib import Path

REPO = Path(r"E:\GraduateDesign\Falcor_Cp")
OUT_DIR = REPO / "build" / "profiling" / "2026-04-06_plan6_phase4"
OUT_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_SCRIPT = REPO / "scripts" / "Voxelization_HybridMeshVoxel.py"
SCENE_PATH = REPO / "Scene" / "Arcade" / "Arcade.pyscene"
RESULT_PATH = OUT_DIR / "phase4_voxel_route_prepare_validation.json"
KEEP_OPEN = os.environ.get("PHASE4_VALIDATE_KEEP_OPEN", "").strip().lower() not in ("", "0", "false", "off", "no")

TARGET_MESH_INSTANCE_ID = int(os.environ.get("PHASE4_TARGET_MESH_INSTANCE_ID", "4"))
TARGET_VOXEL_INSTANCE_ID = int(os.environ.get("PHASE4_TARGET_VOXEL_INSTANCE_ID", "5"))

PASS_TOKENS = (
    "MeshGBuffer",
    "MeshStyleDirectAOPass",
    "HybridBlendMaskPass",
    "VoxelRoutePreparePass",
    "RayMarchingDirectAOPass",
    "HybridCompositePass",
    "ToneMapper",
)

os.environ["HYBRID_OUTPUT_MODE"] = "composite"
os.environ["HYBRID_REFERENCE_VIEW"] = "near"
os.environ["HYBRID_EXECUTION_MODE"] = "ByObjectRoute"
os.environ["HYBRID_SCENE_HINT"] = "Arcade"
os.environ["HYBRID_SCENE_PATH"] = str(SCENE_PATH)
os.environ["HYBRID_VOXELIZATION_BACKEND"] = "CPU"
os.environ["HYBRID_HIDE_UI"] = "1"
os.environ["HYBRID_OPEN_PROFILER"] = "1"
os.environ["HYBRID_FRAMEBUFFER_WIDTH"] = "1600"
os.environ["HYBRID_FRAMEBUFFER_HEIGHT"] = "900"
os.environ["HYBRID_CPU_VOXEL_RESOLUTION"] = "256"
os.environ["HYBRID_CPU_SAMPLE_FREQUENCY"] = "256"
os.environ["HYBRID_CPU_AUTO_GENERATE"] = "0"
os.environ["HYBRID_VOXEL_ROUTE_CONFIDENCE_THRESHOLD"] = os.environ.get("HYBRID_VOXEL_ROUTE_CONFIDENCE_THRESHOLD", "0.95")

with open(GRAPH_SCRIPT, "r", encoding="utf-8") as f:
    exec(compile(f.read(), str(GRAPH_SCRIPT), "exec"), globals(), globals())

m.loadScene(str(SCENE_PATH))
m.clock.pause()
m.profiler.enabled = True
m.profiler.paused = False

print("[validate_phase4] scene:", SCENE_PATH)
print("[validate_phase4] output:", RESULT_PATH)
print("[validate_phase4] keep_open:", KEEP_OPEN)


def pump(frame_count):
    for _ in range(frame_count):
        m.renderFrame()


def compact_info(info):
    return {
        "instance_id": int(info["instance_id"]),
        "node_name": str(info.get("node_name") or ""),
        "geometry_name": str(info.get("geometry_name") or ""),
        "route": str(info.get("route") or ""),
        "resolved_route": str(info.get("resolved_route") or ""),
        "camera_distance_min": float(info["camera_distance_min"]) if info.get("camera_distance_min") is not None else None,
        "camera_distance_max": float(info["camera_distance_max"]) if info.get("camera_distance_max") is not None else None,
        "world_radius": float(info["world_radius"]) if info.get("world_radius") is not None else None,
    }


def get_instance_info(instance_id):
    return next(info for info in m.scene.get_geometry_instance_infos() if int(info["instance_id"]) == int(instance_id))


def get_blend_instance_infos():
    return [compact_info(info) for info in m.scene.get_geometry_instance_infos() if info.get("route") == "Blend"]


def get_filtered_mesh_instance_ids(use_resolved_routes):
    return list(m.scene.get_filtered_mesh_instance_ids(HYBRID_MESH_EXECUTION_ROUTE_MASK, bool(use_resolved_routes)))


def summarize_blend_counts():
    counts = {}
    for info in m.scene.get_geometry_instance_infos():
        if info.get("route") != "Blend":
            continue
        resolved = str(info.get("resolved_route") or "")
        counts[resolved] = counts.get(resolved, 0) + 1
    return counts


def set_camera_for_instance(instance_id, offset_z):
    info = get_instance_info(instance_id)
    center = info["world_bounds"].center
    extent = info["world_bounds"].extent
    camera = m.scene.camera
    camera.position = float3(center.x, center.y + max(0.15, float(extent.y) * 0.25), center.z + float(offset_z))
    camera.target = float3(center.x, center.y, center.z)
    camera.up = float3(0.0, 1.0, 0.0)
    pump(4)
    return compact_info(get_instance_info(instance_id))


def find_first_route_offset(instance_id, target_route, start_offset, end_offset, step):
    samples = []
    offset = float(start_offset)
    while offset <= float(end_offset) + 1e-6:
        info = set_camera_for_instance(instance_id, offset)
        samples.append({"offset_z": round(offset, 4), "info": info})
        if info["resolved_route"] == target_route:
            return offset, info, samples
        offset += float(step)
    return None, samples[-1]["info"] if samples else None, samples


def find_probe_for_route(target_route, start_offset, end_offset, step, preferred_instance_id=-1):
    candidates = get_blend_instance_infos()
    if target_route == "MeshResolved":
        candidates.sort(key=lambda info: (0 if info["instance_id"] == preferred_instance_id else 1, info["world_radius"] or 0.0, info["instance_id"]))
    else:
        candidates.sort(key=lambda info: (0 if info["instance_id"] == preferred_instance_id else 1, -(info["world_radius"] or 0.0), info["instance_id"]))

    attempts = []
    for candidate in candidates:
        offset, info, samples = find_first_route_offset(candidate["instance_id"], target_route, start_offset, end_offset, step)
        attempts.append(
            {
                "target": candidate,
                "matched": offset is not None,
                "offset_z": round(offset, 4) if offset is not None else None,
                "final_info": info,
                "sample_count": len(samples),
            }
        )
        if offset is not None:
            return candidate["instance_id"], offset, info, samples, attempts

    return None, None, None, [], attempts


def filtered_profiler_events():
    events = dict(m.profiler.events)
    return {
        name: value
        for name, value in sorted(events.items())
        if any(token in name for token in PASS_TOKENS)
    }


def extract_gpu_mean(events, token):
    event = next((value for name, value in events.items() if token in name and name.endswith("/gpu_time")), None)
    return float(event["stats"]["mean"]) if event else None


def capture_profile(use_resolved_execution_routes):
    m.activeGraph.updatePass("RayMarchingDirectAOPass", {"useResolvedExecutionRoutes": bool(use_resolved_execution_routes)})
    pump(4)
    m.profiler.reset_stats()
    pump(48)
    return filtered_profiler_events()


print("[validate_phase4] warmup frames: 60")
pump(60)

mesh_probe_instance_id, mesh_offset, mesh_info, mesh_samples, mesh_attempts = find_probe_for_route(
    "MeshResolved",
    0.15,
    1.85,
    0.05,
    preferred_instance_id=TARGET_MESH_INSTANCE_ID,
)
voxel_probe_instance_id, voxel_offset, voxel_info, voxel_samples, voxel_attempts = find_probe_for_route(
    "VoxelResolved",
    2.5,
    7.0,
    0.25,
    preferred_instance_id=TARGET_VOXEL_INSTANCE_ID,
)

if mesh_offset is None:
    raise RuntimeError("Failed to find a MeshResolved probe offset for any Blend instance.")
if voxel_offset is None:
    raise RuntimeError("Failed to find a VoxelResolved probe offset for any Blend instance.")

print("[validate_phase4] mesh probe instance:", mesh_probe_instance_id, "offset:", mesh_offset)
print("[validate_phase4] voxel probe instance:", voxel_probe_instance_id, "offset:", voxel_offset)

set_camera_for_instance(mesh_probe_instance_id, mesh_offset)
mesh_probe = {
    "target": mesh_info,
    "blend_counts": summarize_blend_counts(),
    "offset_z": mesh_offset,
    "samples": mesh_samples,
    "discovery_attempts": mesh_attempts,
    "mesh_instance_ids_authoring": get_filtered_mesh_instance_ids(False),
    "mesh_instance_ids_resolved": get_filtered_mesh_instance_ids(True),
}
mesh_probe["profiler_resolved_off"] = capture_profile(False)
mesh_probe["profiler_resolved_on"] = capture_profile(True)
mesh_probe["gpu_means"] = {
    "route_prepare_gpu_mean": {
        "resolved_off": extract_gpu_mean(mesh_probe["profiler_resolved_off"], "VoxelRoutePreparePass"),
        "resolved_on": extract_gpu_mean(mesh_probe["profiler_resolved_on"], "VoxelRoutePreparePass"),
    },
    "raymarch_gpu_mean": {
        "resolved_off": extract_gpu_mean(mesh_probe["profiler_resolved_off"], "RayMarchingDirectAOPass"),
        "resolved_on": extract_gpu_mean(mesh_probe["profiler_resolved_on"], "RayMarchingDirectAOPass"),
    },
}

set_camera_for_instance(voxel_probe_instance_id, voxel_offset)
voxel_probe = {
    "target": voxel_info,
    "blend_counts": summarize_blend_counts(),
    "offset_z": voxel_offset,
    "samples": voxel_samples,
    "discovery_attempts": voxel_attempts,
    "mesh_instance_ids_authoring": get_filtered_mesh_instance_ids(False),
    "mesh_instance_ids_resolved": get_filtered_mesh_instance_ids(True),
}
voxel_probe["profiler_resolved_off"] = capture_profile(False)
voxel_probe["profiler_resolved_on"] = capture_profile(True)
voxel_probe["gpu_means"] = {
    "raymarch_gpu_mean": {
        "resolved_off": extract_gpu_mean(voxel_probe["profiler_resolved_off"], "RayMarchingDirectAOPass"),
        "resolved_on": extract_gpu_mean(voxel_probe["profiler_resolved_on"], "RayMarchingDirectAOPass"),
    },
}

m.activeGraph.updatePass("RayMarchingDirectAOPass", {"useResolvedExecutionRoutes": True})

summary = {
    "scene": str(SCENE_PATH),
    "active_graph": getattr(m.activeGraph, "name", "<unknown>"),
    "profiler_event_names": sorted(filtered_profiler_events().keys()),
    "mesh_probe": mesh_probe,
    "voxel_probe": voxel_probe,
}

with open(RESULT_PATH, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, sort_keys=True)

print("[validate_phase4] wrote:", RESULT_PATH)
print(json.dumps(summary, indent=2, sort_keys=True))
if KEEP_OPEN:
    print("[validate_phase4] keep_open enabled; leaving Mogwai running.")
else:
    print("[validate_phase4] exiting intentionally after batch validation.")
    exit()
