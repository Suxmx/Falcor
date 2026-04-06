import json
import os
from pathlib import Path

REPO = Path(r"E:\GraduateDesign\Falcor_Cp")
OUT_DIR = REPO / "build" / "profiling" / "2026-04-06_plan6_phase2"
OUT_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_SCRIPT = REPO / "scripts" / "Voxelization_HybridMeshVoxel.py"
SCENE_PATH = REPO / "Scene" / "Arcade" / "Arcade.pyscene"
RESULT_PATH = OUT_DIR / "phase2_resolved_routes_summary.json"
KEEP_OPEN = os.environ.get("PHASE2_VALIDATE_KEEP_OPEN", "").strip().lower() not in ("", "0", "false", "off", "no")

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

with open(GRAPH_SCRIPT, "r", encoding="utf-8") as f:
    exec(compile(f.read(), str(GRAPH_SCRIPT), "exec"), globals(), globals())

m.loadScene(str(SCENE_PATH))
m.clock.pause()
m.profiler.enabled = True
m.profiler.paused = False

print("[validate_phase2] batch validation start")
print("[validate_phase2] scene:", SCENE_PATH)
print("[validate_phase2] output:", RESULT_PATH)
print("[validate_phase2] keep_open:", KEEP_OPEN)


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


def compact_infos(infos):
    return [compact_info(info) for info in infos]


def summarize_view(label, preset):
    print("[validate_phase2] capture view:", label)
    camera = m.scene.camera
    camera.position = float3(*preset["position"])
    camera.target = float3(*preset["target"])
    camera.up = float3(*preset["up"])
    camera.focalLength = preset["focalLength"]
    pump(12)

    infos = list(m.scene.get_geometry_instance_infos())
    blend_infos = [info for info in infos if info.get("route") == "Blend"]

    counts = {}
    for info in blend_infos:
        resolved = str(info.get("resolved_route") or "")
        counts[resolved] = counts.get(resolved, 0) + 1

    samples = {}
    for resolved_name in ("MeshResolved", "VoxelResolved", "NeedsBoth"):
        sample = next((info for info in blend_infos if info.get("resolved_route") == resolved_name), None)
        samples[resolved_name] = compact_info(sample) if sample else None

    return {
        "blend_counts": counts,
        "blend_infos": compact_infos(blend_infos),
        "all_instance_infos": compact_infos(infos),
        "samples": samples,
    }


print("[validate_phase2] warmup frames: 180")
pump(180)
summary = {
    "scene": str(SCENE_PATH),
    "active_graph": getattr(m.activeGraph, "name", "<unknown>"),
    "profiler_events": sorted(
        name
        for name in dict(m.profiler.events).keys()
        if any(token in name for token in (
            "MeshGBuffer",
            "MeshStyleDirectAOPass",
            "HybridBlendMaskPass",
            "RayMarchingDirectAOPass",
            "HybridCompositePass",
            "ToneMapper",
        ))
    ),
    "views": {
        "near": summarize_view("near", ARCADE_REFERENCE_VIEWS["near"]),
        "mid": summarize_view("mid", ARCADE_REFERENCE_VIEWS["mid"]),
        "far": summarize_view("far", ARCADE_REFERENCE_VIEWS["far"]),
    },
}

with open(RESULT_PATH, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, sort_keys=True)

print("[validate_phase2] validation finished")
print("[validate_phase2] wrote:", RESULT_PATH)
print(json.dumps(summary, indent=2, sort_keys=True))
if KEEP_OPEN:
    print("[validate_phase2] keep_open enabled; leaving Mogwai running.")
else:
    print("[validate_phase2] exiting intentionally after batch validation.")
    exit()
