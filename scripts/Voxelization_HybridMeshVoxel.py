import falcor
import os
import re


def env_bool(name, default):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.lower() not in ("0", "false", "off", "no")


def env_int(name, default):
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_float(name, default):
    value = os.environ.get(name)
    return float(value) if value not in (None, "") else default


def parse_float3(value):
    if value in (None, ""):
        return None

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Expected three comma-separated values, got: {value}")
    return tuple(float(part) for part in parts)


ARCADE_REFERENCE_VIEWS = {
    "near": {
        "position": (-0.811894, 1.575547, 1.825012),
        "target": (-0.370011, 1.218823, 1.001915),
        "up": (-0.376237, 0.634521, 0.675103),
        "focalLength": 21.0,
    },
    "mid": {
        "position": (-1.143306, 1.843090, 2.442334),
        "target": (-0.701423, 1.486366, 1.619238),
        "up": (-0.376237, 0.634521, 0.675103),
        "focalLength": 21.0,
    },
    "far": {
        "position": (-1.585189, 2.199814, 3.265431),
        "target": (-1.143306, 1.843090, 2.442334),
        "up": (-0.376237, 0.634521, 0.675103),
        "focalLength": 21.0,
    },
}


REFERENCE_VIEWS_BY_SCENE = {
    "arcade": ARCADE_REFERENCE_VIEWS,
}

ARCADE_REFERENCE_ROUTES = []

REFERENCE_ROUTES_BY_SCENE = {
    "arcade": ARCADE_REFERENCE_ROUTES,
}

DEBUG_VIEW_MODES = {
    "baseshading": "BaseShading",
    "albedo": "Albedo",
    "normal": "Normal",
    "depth": "Depth",
    "emissive": "Emissive",
    "specular": "Specular",
    "roughness": "Roughness",
    "route": "RouteDebug",
    "routedebug": "RouteDebug",
}

STYLE_VIEW_MODES = {
    "combined": "Combined",
    "directonly": "DirectOnly",
    "aoonly": "AOOnly",
}

COMPOSITE_VIEW_MODES = {
    "composite": "Composite",
    "meshonly": "MeshOnly",
    "voxelonly": "VoxelOnly",
    "blendmask": "BlendMask",
    "routedebug": "RouteDebug",
    "voxeldepth": "VoxelDepth",
    "voxelnormal": "VoxelNormal",
    "voxelconfidence": "VoxelConfidence",
    "voxelroute": "VoxelRouteID",
    "voxelrouteid": "VoxelRouteID",
    "voxelinstance": "VoxelInstanceID",
    "voxelinstanceid": "VoxelInstanceID",
    "objectmismatch": "ObjectMismatch",
    "depthmismatch": "DepthMismatch",
}

HYBRID_EXECUTION_MODES = {
    "byobjectroute": "ByObjectRoute",
    "forcemeshpipeline": "ForceMeshPipeline",
    "forcevoxelpipeline": "ForceVoxelPipeline",
}

RUNTIME_GRAPH_NAME_BY_EXECUTION_MODE = {
    "ByObjectRoute": "ByObjectRoute",
    "ForceMeshPipeline": "MeshOnly",
    "ForceVoxelPipeline": "VoxelOnly",
}

ROUTE_NAME_MAP = {
    "blend": "Blend",
    "mesh": "MeshOnly",
    "meshonly": "MeshOnly",
    "voxel": "VoxelOnly",
    "voxelonly": "VoxelOnly",
}

ROUTE_MASK_BLEND = 1 << 0
ROUTE_MASK_MESH_ONLY = 1 << 1
ROUTE_MASK_VOXEL_ONLY = 1 << 2
HYBRID_MESH_EXECUTION_ROUTE_MASK = ROUTE_MASK_BLEND | ROUTE_MASK_MESH_ONLY
HYBRID_VOXEL_EXECUTION_ROUTE_MASK = ROUTE_MASK_BLEND | ROUTE_MASK_VOXEL_ONLY
HYBRID_RUNTIME_RESOLVED_ROUTE_SOURCE = None
HYBRID_RUNTIME_RESOLVED_ROUTE_STATE = {"signature": None}


def resolve_output_mode():
    requested = (os.environ.get("HYBRID_OUTPUT_MODE", "Composite").strip() or "Composite").lower()
    if requested == "meshview":
        return "MeshView", "mesh"
    if requested in COMPOSITE_VIEW_MODES:
        return COMPOSITE_VIEW_MODES[requested], "hybrid"

    valid = sorted(list(COMPOSITE_VIEW_MODES.values()) + ["MeshView"])
    raise RuntimeError(f"Unsupported HYBRID_OUTPUT_MODE: {requested}. Expected one of: {', '.join(valid)}")


def resolve_execution_mode():
    requested = (os.environ.get("HYBRID_EXECUTION_MODE", "ByObjectRoute").strip() or "ByObjectRoute").lower()
    if requested in HYBRID_EXECUTION_MODES:
        return HYBRID_EXECUTION_MODES[requested]

    valid = sorted(set(HYBRID_EXECUTION_MODES.values()))
    raise RuntimeError(f"Unsupported HYBRID_EXECUTION_MODE: {requested}. Expected one of: {', '.join(valid)}")


def resolve_voxel_backend():
    backend = os.environ.get("HYBRID_VOXELIZATION_BACKEND", "CPU").strip().upper()
    return backend if backend in ("CPU", "GPU") else "CPU"


CACHE_NAME_RE = re.compile(r"^(?P<prefix>.+)_\((?P<x>\d+), (?P<y>\d+), (?P<z>\d+)\)_(?P<sample>\d+)\.bin_(?P<backend>CPU|GPU)$", re.IGNORECASE)


def list_scene_cache_infos(scene_name_hint=""):
    resource_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resource")
    infos = []
    if not os.path.isdir(resource_dir):
        return resource_dir, infos

    hint = scene_name_hint.lower()
    for filename in sorted(os.listdir(resource_dir)):
        match = CACHE_NAME_RE.match(filename)
        if not match:
            continue
        lower = filename.lower()
        if hint and hint not in lower:
            continue
        infos.append(
            {
                "filename": filename,
                "path": os.path.join(resource_dir, filename),
                "prefix": match.group("prefix"),
                "voxel_count": (
                    int(match.group("x")),
                    int(match.group("y")),
                    int(match.group("z")),
                ),
                "sample_frequency": int(match.group("sample")),
                "backend": match.group("backend").upper(),
            }
        )

    return resource_dir, infos


def choose_cache_plan(scene_name_hint="", backend="CPU", allow_fallback=False):
    resource_dir, infos = list_scene_cache_infos(scene_name_hint)
    preferred = next((info for info in infos if info["backend"] == backend), None)
    reference = preferred or (infos[0] if infos else None)

    inferred_resolution = None
    inferred_sample_frequency = None
    desired_path = ""
    desired_exists = False

    if reference:
        inferred_resolution = max(reference["voxel_count"])
        inferred_sample_frequency = reference["sample_frequency"]
        desired_filename = (
            f'{reference["prefix"]}_({reference["voxel_count"][0]}, {reference["voxel_count"][1]}, {reference["voxel_count"][2]})_'
            f'{reference["sample_frequency"]}.bin_{backend}'
        )
        desired_path = os.path.join(resource_dir, desired_filename)
        desired_exists = os.path.exists(desired_path)

    bin_file = ""
    if preferred:
        bin_file = preferred["path"]
    elif backend == "CPU" and desired_path:
        bin_file = desired_path
    elif allow_fallback and reference:
        bin_file = reference["path"]

    return {
        "bin_file": bin_file,
        "desired_path": desired_path,
        "desired_exists": desired_exists,
        "voxel_resolution": inferred_resolution,
        "sample_frequency": inferred_sample_frequency,
    }


def resolve_scene_hint():
    for key in ("HYBRID_SCENE_PATH", "HYBRID_SCENE_HINT"):
        value = os.environ.get(key, "").strip()
        if value:
            return os.path.basename(value).split(".")[0]

    try:
        if m.scene:
            return os.path.basename(str(m.scene.path)).split(".")[0]
    except Exception:
        pass

    return ""


def resolve_reference_view(scene_hint, reference_view_name):
    if not reference_view_name:
        return None

    presets = REFERENCE_VIEWS_BY_SCENE.get(scene_hint.lower())
    if not presets:
        return None

    return presets.get(reference_view_name.lower())


def resolve_camera_plan(scene_hint):
    reference_view_name = os.environ.get("HYBRID_REFERENCE_VIEW", "").strip()
    preset = resolve_reference_view(scene_hint, reference_view_name)
    position = parse_float3(os.environ.get("HYBRID_CAMERA_POSITION"))
    target = parse_float3(os.environ.get("HYBRID_CAMERA_TARGET"))
    up = parse_float3(os.environ.get("HYBRID_CAMERA_UP"))
    focal_length = env_float("HYBRID_CAMERA_FOCAL_LENGTH", 0.0)

    if preset:
        position = position or preset["position"]
        target = target or preset["target"]
        up = up or preset["up"]
        if focal_length <= 0.0:
            focal_length = preset["focalLength"]

    if position is None and target is None and up is None and focal_length <= 0.0:
        return None

    return {
        "reference_view": reference_view_name,
        "position": position,
        "target": target,
        "up": up,
        "focal_length": focal_length,
    }


def resolve_mesh_view_mode():
    requested = (os.environ.get("HYBRID_MESH_VIEW_MODE", "Combined").strip() or "Combined").lower()
    if requested in STYLE_VIEW_MODES:
        return STYLE_VIEW_MODES[requested], "style"
    if requested in DEBUG_VIEW_MODES:
        return DEBUG_VIEW_MODES[requested], "debug"

    valid = sorted(set(STYLE_VIEW_MODES.values()) | set(DEBUG_VIEW_MODES.values()))
    raise RuntimeError(f"Unsupported HYBRID_MESH_VIEW_MODE: {requested}. Expected one of: {', '.join(valid)}")


def normalize_route_name(route_name):
    key = (route_name or "").strip().lower()
    if key in ROUTE_NAME_MAP:
        return ROUTE_NAME_MAP[key]
    raise RuntimeError(f"Unsupported route name: {route_name}. Expected one of: Blend, MeshOnly, VoxelOnly")


def parse_route_overrides():
    raw_value = os.environ.get("HYBRID_ROUTE_OVERRIDES", "").strip()
    if not raw_value:
        return {}

    overrides = {}
    entries = [entry.strip() for entry in raw_value.replace(";", ",").split(",") if entry.strip()]
    for entry in entries:
        if ":" not in entry:
            raise RuntimeError(f"Invalid HYBRID_ROUTE_OVERRIDES entry: {entry}. Expected Name:Route")
        match_name, route_name = [part.strip() for part in entry.split(":", 1)]
        if not match_name:
            raise RuntimeError(f"Invalid HYBRID_ROUTE_OVERRIDES entry: {entry}. Missing object name")
        overrides[match_name.lower()] = {"label": match_name, "match": match_name, "route": normalize_route_name(route_name)}

    return overrides


def resolve_reference_routes(scene_hint):
    route_specs = [dict(spec) for spec in REFERENCE_ROUTES_BY_SCENE.get(scene_hint.lower(), [])]
    overrides = parse_route_overrides()
    if not overrides:
        return route_specs

    consumed = set()
    for spec in route_specs:
        override = overrides.get(spec["match"].lower())
        if not override:
            continue
        spec["label"] = override["label"]
        spec["match"] = override["match"]
        spec["route"] = override["route"]
        consumed.add(spec["match"].lower())

    for match_name, override in overrides.items():
        if match_name not in consumed:
            route_specs.append(dict(override))

    return route_specs


def try_match_reference_instances(instance_infos, match_name):
    needle = match_name.lower()

    node_matches = [info["instance_id"] for info in instance_infos if (info.get("node_name") or "").lower() == needle]
    if node_matches:
        return node_matches, "node"

    geometry_matches = [info["instance_id"] for info in instance_infos if (info.get("geometry_name") or "").lower() == needle]
    if geometry_matches:
        return geometry_matches, "geometry"

    fuzzy_matches = [
        info["instance_id"]
        for info in instance_infos
        if needle in (info.get("node_name") or "").lower() or needle in (info.get("geometry_name") or "").lower()
    ]
    if fuzzy_matches:
        return fuzzy_matches, "fuzzy"

    return [], "none"


def apply_reference_routes(scene, scene_hint):
    route_specs = resolve_reference_routes(scene_hint)
    if scene is None or not route_specs:
        return True

    instance_infos = list(scene.get_geometry_instance_infos())
    applied = []
    unresolved = []

    for spec in route_specs:
        instance_ids, match_mode = try_match_reference_instances(instance_infos, spec["match"])
        if not instance_ids:
            unresolved.append(spec["match"])
            continue

        for instance_id in instance_ids:
            scene.set_geometry_instance_route(instance_id, spec["route"])

        applied.append(
            {
                "label": spec["label"],
                "route": spec["route"],
                "instance_ids": instance_ids,
                "match_mode": match_mode,
            }
        )

    if applied:
        print("[HybridMeshVoxel] reference routes:")
        for item in applied:
            print(
                "  -",
                item["label"],
                "->",
                item["route"],
                f"(ids={item['instance_ids']}, match={item['match_mode']})",
            )

    if unresolved:
        print("[HybridMeshVoxel] unresolved route refs:", ", ".join(unresolved))

    return True


def set_runtime_resolved_route_source(source):
    global HYBRID_RUNTIME_RESOLVED_ROUTE_SOURCE, HYBRID_RUNTIME_RESOLVED_ROUTE_STATE
    HYBRID_RUNTIME_RESOLVED_ROUTE_SOURCE = source
    HYBRID_RUNTIME_RESOLVED_ROUTE_STATE = {"signature": None}


def resolve_runtime_resolved_route_config():
    if HYBRID_RUNTIME_RESOLVED_ROUTE_SOURCE is None:
        return False, 0.0, 0.0

    props = HYBRID_RUNTIME_RESOLVED_ROUTE_SOURCE.properties
    blend_start_distance = max(0.0, float(props.get("blendStartDistance", 0.0)))
    blend_end_distance = max(blend_start_distance, float(props.get("blendEndDistance", blend_start_distance)))
    return True, blend_start_distance, blend_end_distance


def sync_scene_resolved_route_config(scene):
    global HYBRID_RUNTIME_RESOLVED_ROUTE_STATE
    if scene is None:
        return

    enabled, blend_start_distance, blend_end_distance = resolve_runtime_resolved_route_config()
    scene.set_geometry_instance_resolved_route_config(blend_start_distance, blend_end_distance, enabled)

    signature = (enabled, round(blend_start_distance, 6), round(blend_end_distance, 6))
    if HYBRID_RUNTIME_RESOLVED_ROUTE_STATE.get("signature") == signature:
        return

    HYBRID_RUNTIME_RESOLVED_ROUTE_STATE["signature"] = signature
    if enabled:
        print(
            "[HybridMeshVoxel] resolved route band:",
            f"{blend_start_distance:.2f} -> {blend_end_distance:.2f}",
        )
    else:
        print("[HybridMeshVoxel] resolved route band: disabled")


def apply_renderer_overrides(scene_hint, camera_plan, default_framebuffer=None):
    hide_ui = env_bool("HYBRID_HIDE_UI", False)
    open_profiler = env_bool("HYBRID_OPEN_PROFILER", True)
    default_width, default_height = default_framebuffer if default_framebuffer else (0, 0)
    framebuffer_width = env_int("HYBRID_FRAMEBUFFER_WIDTH", default_width)
    framebuffer_height = env_int("HYBRID_FRAMEBUFFER_HEIGHT", default_height)

    if hide_ui:
        m.ui = False

    try:
        m.profiler.enabled = open_profiler
    except Exception:
        pass

    if framebuffer_width > 0 and framebuffer_height > 0:
        m.resizeFrameBuffer(framebuffer_width, framebuffer_height)

    route_specs = resolve_reference_routes(scene_hint)
    wait_for_scene_hint = not bool(scene_hint)
    needs_continuous_updates = HYBRID_RUNTIME_RESOLVED_ROUTE_SOURCE is not None
    if not camera_plan and not route_specs and not wait_for_scene_hint and not needs_continuous_updates:
        return

    setup_state = {
        "camera_done": camera_plan is None,
        "routes_done": not route_specs and not wait_for_scene_hint,
    }

    def apply_scene_setup_once(scene, current_time):
        if scene is None:
            return

        if not setup_state["routes_done"]:
            effective_scene_hint = scene_hint or resolve_scene_hint()
            effective_route_specs = resolve_reference_routes(effective_scene_hint)
            if effective_route_specs:
                setup_state["routes_done"] = apply_reference_routes(scene, effective_scene_hint)
            elif effective_scene_hint:
                setup_state["routes_done"] = True

        if not setup_state["camera_done"] and scene.camera is not None:
            camera = scene.camera
            if camera_plan["position"] is not None:
                camera.position = falcor.float3(*camera_plan["position"])
            if camera_plan["target"] is not None:
                camera.target = falcor.float3(*camera_plan["target"])
            if camera_plan["up"] is not None:
                camera.up = falcor.float3(*camera_plan["up"])
            if camera_plan["focal_length"] > 0.0:
                camera.focalLength = camera_plan["focal_length"]

            setup_state["camera_done"] = True
            print(
                "[HybridMeshVoxel] camera:",
                camera_plan["reference_view"] if camera_plan["reference_view"] else "<explicit>",
            )

        sync_scene_resolved_route_config(scene)

        if setup_state["camera_done"] and setup_state["routes_done"] and not needs_continuous_updates:
            m.sceneUpdateCallback = None

    try:
        apply_scene_setup_once(m.scene, 0.0)
    except Exception:
        pass

    if not (setup_state["camera_done"] and setup_state["routes_done"]) or needs_continuous_updates:
        m.sceneUpdateCallback = apply_scene_setup_once


def log_graph_passes(graph_name, pass_names):
    print("[HybridMeshVoxel] graph:", graph_name)
    print("[HybridMeshVoxel] passes:", ", ".join(pass_names))


def connect_mesh_gbuffer(g, source_name, target_name):
    g.addEdge(f"{source_name}.posW", f"{target_name}.posW")
    g.addEdge(f"{source_name}.normW", f"{target_name}.normW")
    g.addEdge(f"{source_name}.faceNormalW", f"{target_name}.faceNormalW")
    g.addEdge(f"{source_name}.viewW", f"{target_name}.viewW")
    g.addEdge(f"{source_name}.diffuseOpacity", f"{target_name}.diffuseOpacity")
    g.addEdge(f"{source_name}.specRough", f"{target_name}.specRough")


def create_mesh_gbuffer(instance_route_mask=None, use_resolved_execution_routes=False):
    props = {
        "outputSize": "Default",
        "samplePattern": "Center",
        "useAlphaTest": True,
        "adjustShadingNormals": True,
    }
    if instance_route_mask is not None:
        props["instanceRouteMask"] = int(instance_route_mask)
    if use_resolved_execution_routes:
        props["useResolvedExecutionRoutes"] = True
    return createPass("GBufferRaster", props)


def create_mesh_style_pass(shadow_bias, render_background, ao_enabled, ao_strength, ao_radius, ao_step_count, ao_direction_set, ao_contact_strength, ao_use_stable_rotation):
    return createPass(
        "MeshStyleDirectAOPass",
        {
            "viewMode": "Combined",
            "shadowBias": shadow_bias,
            "renderBackground": render_background,
            "aoEnabled": ao_enabled,
            "aoStrength": ao_strength,
            "aoRadius": ao_radius,
            "aoStepCount": ao_step_count,
            "aoDirectionSet": ao_direction_set,
            "aoContactStrength": ao_contact_strength,
            "aoUseStableRotation": ao_use_stable_rotation,
        },
    )


def create_voxel_chain(scene_hint, instance_route_mask=HYBRID_VOXEL_EXECUTION_ROUTE_MASK):
    voxel_backend = resolve_voxel_backend()
    allow_cache_fallback = env_bool("HYBRID_ALLOW_CACHE_FALLBACK", False)
    cache_plan = choose_cache_plan(scene_hint, voxel_backend, allow_cache_fallback)
    voxel_pass_name = "VoxelizationPass_CPU" if voxel_backend == "CPU" else "VoxelizationPass_GPU"
    voxel_pass_props = {}

    if voxel_backend == "CPU":
        cpu_voxel_resolution = env_int("HYBRID_CPU_VOXEL_RESOLUTION", cache_plan["voxel_resolution"] or 128)
        cpu_sample_frequency = env_int("HYBRID_CPU_SAMPLE_FREQUENCY", cache_plan["sample_frequency"] or 256)
        voxel_pass_props = {
            "sceneName": "Auto",
            "voxelResolution": cpu_voxel_resolution,
            "sampleFrequency": cpu_sample_frequency,
            "polygonPerFrame": env_int("HYBRID_CPU_POLYGON_PER_FRAME", 256000),
            "lerpNormal": env_bool("HYBRID_CPU_LERP_NORMAL", False),
            "autoGenerate": env_bool(
                "HYBRID_CPU_AUTO_GENERATE",
                bool(cache_plan["desired_path"]) and not cache_plan["desired_exists"],
            ),
        }

    voxel_output_resolution = env_int("HYBRID_VOXEL_OUTPUT_RESOLUTION", 0)
    voxel_pass = createPass(voxel_pass_name, voxel_pass_props)
    read_pass = createPass("ReadVoxelPass", {"binFile": cache_plan["bin_file"]} if cache_plan["bin_file"] else {})
    marching_pass_props = {
        "drawMode": 0,
        "outputResolution": voxel_output_resolution,
        "checkEllipsoid": env_bool("HYBRID_VOXEL_CHECK_ELLIPSOID", True),
        "checkVisibility": env_bool("HYBRID_VOXEL_CHECK_VISIBILITY", True),
        "checkCoverage": env_bool("HYBRID_VOXEL_CHECK_COVERAGE", True),
        "useMipmap": env_bool("HYBRID_VOXEL_USE_MIPMAP", True),
        "renderBackground": env_bool("HYBRID_VOXEL_RENDER_BACKGROUND", True),
        "transmittanceThreshold": env_float("HYBRID_VOXEL_TRANSMITTANCE_THRESHOLD", 5.0),
        "aoEnabled": env_bool("HYBRID_VOXEL_AO_ENABLED", True),
        "aoStrength": env_float("HYBRID_VOXEL_AO_STRENGTH", 0.55),
        "aoRadius": env_float("HYBRID_VOXEL_AO_RADIUS", 6.0),
        "aoStepCount": env_int("HYBRID_VOXEL_AO_STEP_COUNT", 3),
        "aoDirectionSet": env_int("HYBRID_VOXEL_AO_DIRECTION_SET", 6),
        "aoContactStrength": env_float("HYBRID_VOXEL_AO_CONTACT_STRENGTH", 0.75),
        "aoUseStableRotation": env_bool("HYBRID_VOXEL_AO_USE_STABLE_ROTATION", True),
    }
    if instance_route_mask is not None:
        marching_pass_props["instanceRouteMask"] = int(instance_route_mask)
    marching_pass = createPass("RayMarchingDirectAOPass", marching_pass_props)

    return {
        "backend": voxel_backend,
        "cache_plan": cache_plan,
        "output_resolution": voxel_output_resolution,
        "voxel_pass": voxel_pass,
        "read_pass": read_pass,
        "marching_pass": marching_pass,
    }


def resolve_voxel_default_framebuffer(voxel_output_resolution):
    if voxel_output_resolution > 0:
        return (voxel_output_resolution, voxel_output_resolution)
    return (1920, 1080)


def render_graph_mesh_view(scene_hint, camera_plan):
    view_mode, pipeline = resolve_mesh_view_mode()
    depth_range = env_float("HYBRID_MESH_DEPTH_RANGE", 12.0)
    shadow_bias = env_float("HYBRID_MESH_SHADOW_BIAS", 0.001)
    render_background = env_bool("HYBRID_MESH_RENDER_BACKGROUND", True)
    ao_enabled = env_bool("HYBRID_MESH_AO_ENABLED", True)
    ao_strength = env_float("HYBRID_MESH_AO_STRENGTH", 0.55)
    ao_radius = env_float("HYBRID_MESH_AO_RADIUS", 0.18)
    ao_step_count = env_int("HYBRID_MESH_AO_STEP_COUNT", 3)
    ao_direction_set = env_int("HYBRID_MESH_AO_DIRECTION_SET", 6)
    ao_contact_strength = env_float("HYBRID_MESH_AO_CONTACT_STRENGTH", 0.75)
    ao_use_stable_rotation = env_bool("HYBRID_MESH_AO_USE_STABLE_ROTATION", True)

    print("[HybridMeshVoxel] pipeline:", pipeline)
    print("[HybridMeshVoxel] mesh view mode:", view_mode)

    g = RenderGraph("VoxelizationHybridMeshVoxelMeshView")

    mesh_gbuffer = create_mesh_gbuffer()
    tone_mapper = createPass("ToneMapper", {"autoExposure": False, "exposureCompensation": 0.0})

    g.addPass(mesh_gbuffer, "MeshGBuffer")
    g.addPass(tone_mapper, "ToneMapper")

    if pipeline == "style":
        mesh_style = createPass(
            "MeshStyleDirectAOPass",
            {
                "viewMode": view_mode,
                "shadowBias": shadow_bias,
                "renderBackground": render_background,
                "aoEnabled": ao_enabled,
                "aoStrength": ao_strength,
                "aoRadius": ao_radius,
                "aoStepCount": ao_step_count,
                "aoDirectionSet": ao_direction_set,
                "aoContactStrength": ao_contact_strength,
                "aoUseStableRotation": ao_use_stable_rotation,
            },
        )
        g.addPass(mesh_style, "MeshStyleDirectAOPass")
        connect_mesh_gbuffer(g, "MeshGBuffer", "MeshStyleDirectAOPass")
        g.addEdge("MeshStyleDirectAOPass.color", "ToneMapper.src")
    else:
        mesh_debug = createPass(
            "HybridMeshDebugPass",
            {
                "viewMode": view_mode,
                "depthRange": depth_range,
                "renderBackground": render_background,
            },
        )
        g.addPass(mesh_debug, "HybridMeshDebugPass")
        connect_mesh_gbuffer(g, "MeshGBuffer", "HybridMeshDebugPass")
        g.addEdge("MeshGBuffer.emissive", "HybridMeshDebugPass.emissive")
        g.addEdge("MeshGBuffer.vbuffer", "HybridMeshDebugPass.vbuffer")
        g.addEdge("HybridMeshDebugPass.color", "ToneMapper.src")

    g.markOutput("ToneMapper.dst")
    log_graph_passes(
        "VoxelizationHybridMeshVoxelMeshView",
        ["MeshGBuffer", "MeshStyleDirectAOPass", "ToneMapper"] if pipeline == "style" else ["MeshGBuffer", "HybridMeshDebugPass", "ToneMapper"],
    )
    apply_renderer_overrides(scene_hint, camera_plan)
    return g


def render_graph_hybrid(scene_hint, camera_plan, output_mode, graph_name=None):
    shadow_bias = env_float("HYBRID_MESH_SHADOW_BIAS", 0.001)
    render_background = env_bool("HYBRID_MESH_RENDER_BACKGROUND", True)
    ao_enabled = env_bool("HYBRID_MESH_AO_ENABLED", True)
    ao_strength = env_float("HYBRID_MESH_AO_STRENGTH", 0.55)
    ao_radius = env_float("HYBRID_MESH_AO_RADIUS", 0.18)
    ao_step_count = env_int("HYBRID_MESH_AO_STEP_COUNT", 3)
    ao_direction_set = env_int("HYBRID_MESH_AO_DIRECTION_SET", 6)
    ao_contact_strength = env_float("HYBRID_MESH_AO_CONTACT_STRENGTH", 0.75)
    ao_use_stable_rotation = env_bool("HYBRID_MESH_AO_USE_STABLE_ROTATION", True)
    blend_start_distance = env_float("HYBRID_BLEND_START_DISTANCE", 1.50)
    blend_end_distance = env_float("HYBRID_BLEND_END_DISTANCE", 3.25)
    blend_exponent = env_float("HYBRID_BLEND_EXPONENT", 1.0)

    voxel_chain = create_voxel_chain(scene_hint)
    print("[HybridMeshVoxel] voxel backend:", voxel_chain["backend"])
    print("[HybridMeshVoxel] voxel cache:", voxel_chain["cache_plan"]["bin_file"] if voxel_chain["cache_plan"]["bin_file"] else "<none>")
    print(
        "[HybridMeshVoxel] blend distances:",
        f"{blend_start_distance:.2f} -> {blend_end_distance:.2f}",
        f"(exp={blend_exponent:.2f})",
    )

    g = RenderGraph(graph_name or "ByObjectRoute")

    mesh_gbuffer = create_mesh_gbuffer(HYBRID_MESH_EXECUTION_ROUTE_MASK, use_resolved_execution_routes=True)
    mesh_style = create_mesh_style_pass(
        shadow_bias,
        render_background,
        ao_enabled,
        ao_strength,
        ao_radius,
        ao_step_count,
        ao_direction_set,
        ao_contact_strength,
        ao_use_stable_rotation,
    )
    blend_mask = createPass(
        "HybridBlendMaskPass",
        {
            "blendStartDistance": blend_start_distance,
            "blendEndDistance": blend_end_distance,
            "blendExponent": blend_exponent,
        },
    )
    set_runtime_resolved_route_source(blend_mask)
    composite = createPass("HybridCompositePass", {"viewMode": output_mode})
    tone_mapper = createPass("ToneMapper", {"autoExposure": False, "exposureCompensation": 0.0})

    g.addPass(mesh_gbuffer, "MeshGBuffer")
    g.addPass(mesh_style, "MeshStyleDirectAOPass")
    g.addPass(blend_mask, "HybridBlendMaskPass")
    g.addPass(voxel_chain["voxel_pass"], "VoxelizationPass")
    g.addPass(voxel_chain["read_pass"], "ReadVoxelPass")
    g.addPass(voxel_chain["marching_pass"], "RayMarchingDirectAOPass")
    g.addPass(composite, "HybridCompositePass")
    g.addPass(tone_mapper, "ToneMapper")

    connect_mesh_gbuffer(g, "MeshGBuffer", "MeshStyleDirectAOPass")
    g.addEdge("MeshGBuffer.posW", "HybridBlendMaskPass.posW")
    g.addEdge("MeshGBuffer.vbuffer", "HybridBlendMaskPass.vbuffer")

    g.addEdge("VoxelizationPass.dummy", "ReadVoxelPass.dummy")
    g.addEdge("ReadVoxelPass.vBuffer", "RayMarchingDirectAOPass.vBuffer")
    g.addEdge("ReadVoxelPass.gBuffer", "RayMarchingDirectAOPass.gBuffer")
    g.addEdge("ReadVoxelPass.pBuffer", "RayMarchingDirectAOPass.pBuffer")
    g.addEdge("ReadVoxelPass.blockMap", "RayMarchingDirectAOPass.blockMap")

    g.addEdge("MeshStyleDirectAOPass.color", "HybridCompositePass.meshColor")
    g.addEdge("MeshGBuffer.posW", "HybridCompositePass.meshPosW")
    g.addEdge("RayMarchingDirectAOPass.color", "HybridCompositePass.voxelColor")
    g.addEdge("RayMarchingDirectAOPass.voxelDepth", "HybridCompositePass.voxelDepth")
    g.addEdge("RayMarchingDirectAOPass.voxelNormal", "HybridCompositePass.voxelNormal")
    g.addEdge("RayMarchingDirectAOPass.voxelConfidence", "HybridCompositePass.voxelConfidence")
    g.addEdge("RayMarchingDirectAOPass.voxelInstanceID", "HybridCompositePass.voxelInstanceID")
    g.addEdge("HybridBlendMaskPass.mask", "HybridCompositePass.blendMask")
    g.addEdge("MeshGBuffer.vbuffer", "HybridCompositePass.vbuffer")
    g.addEdge("HybridCompositePass.color", "ToneMapper.src")
    g.markOutput("ToneMapper.dst")

    log_graph_passes(
        g.name,
        [
            "MeshGBuffer",
            "MeshStyleDirectAOPass",
            "HybridBlendMaskPass",
            "VoxelizationPass",
            "ReadVoxelPass",
            "RayMarchingDirectAOPass",
            "HybridCompositePass",
            "ToneMapper",
        ],
    )

    default_framebuffer = resolve_voxel_default_framebuffer(voxel_chain["output_resolution"])
    apply_renderer_overrides(scene_hint, camera_plan, default_framebuffer)
    return g


def render_graph_force_mesh(scene_hint, camera_plan, graph_name=None):
    shadow_bias = env_float("HYBRID_MESH_SHADOW_BIAS", 0.001)
    render_background = env_bool("HYBRID_MESH_RENDER_BACKGROUND", True)
    ao_enabled = env_bool("HYBRID_MESH_AO_ENABLED", True)
    ao_strength = env_float("HYBRID_MESH_AO_STRENGTH", 0.55)
    ao_radius = env_float("HYBRID_MESH_AO_RADIUS", 0.18)
    ao_step_count = env_int("HYBRID_MESH_AO_STEP_COUNT", 3)
    ao_direction_set = env_int("HYBRID_MESH_AO_DIRECTION_SET", 6)
    ao_contact_strength = env_float("HYBRID_MESH_AO_CONTACT_STRENGTH", 0.75)
    ao_use_stable_rotation = env_bool("HYBRID_MESH_AO_USE_STABLE_ROTATION", True)

    g = RenderGraph(graph_name or "MeshOnly")

    mesh_gbuffer = create_mesh_gbuffer()
    mesh_style = create_mesh_style_pass(
        shadow_bias,
        render_background,
        ao_enabled,
        ao_strength,
        ao_radius,
        ao_step_count,
        ao_direction_set,
        ao_contact_strength,
        ao_use_stable_rotation,
    )
    tone_mapper = createPass("ToneMapper", {"autoExposure": False, "exposureCompensation": 0.0})

    g.addPass(mesh_gbuffer, "MeshGBuffer")
    g.addPass(mesh_style, "MeshStyleDirectAOPass")
    g.addPass(tone_mapper, "ToneMapper")

    connect_mesh_gbuffer(g, "MeshGBuffer", "MeshStyleDirectAOPass")
    g.addEdge("MeshStyleDirectAOPass.color", "ToneMapper.src")
    g.markOutput("ToneMapper.dst")

    log_graph_passes(
        g.name,
        ["MeshGBuffer", "MeshStyleDirectAOPass", "ToneMapper"],
    )
    apply_renderer_overrides(scene_hint, camera_plan)
    return g


def render_graph_force_voxel(scene_hint, camera_plan, graph_name=None):
    voxel_chain = create_voxel_chain(scene_hint, instance_route_mask=None)
    print("[HybridMeshVoxel] voxel backend:", voxel_chain["backend"])
    print("[HybridMeshVoxel] voxel cache:", voxel_chain["cache_plan"]["bin_file"] if voxel_chain["cache_plan"]["bin_file"] else "<none>")

    g = RenderGraph(graph_name or "VoxelOnly")
    tone_mapper = createPass("ToneMapper", {"autoExposure": False, "exposureCompensation": 0.0})

    g.addPass(voxel_chain["voxel_pass"], "VoxelizationPass")
    g.addPass(voxel_chain["read_pass"], "ReadVoxelPass")
    g.addPass(voxel_chain["marching_pass"], "RayMarchingDirectAOPass")
    g.addPass(tone_mapper, "ToneMapper")

    g.addEdge("VoxelizationPass.dummy", "ReadVoxelPass.dummy")
    g.addEdge("ReadVoxelPass.vBuffer", "RayMarchingDirectAOPass.vBuffer")
    g.addEdge("ReadVoxelPass.gBuffer", "RayMarchingDirectAOPass.gBuffer")
    g.addEdge("ReadVoxelPass.pBuffer", "RayMarchingDirectAOPass.pBuffer")
    g.addEdge("ReadVoxelPass.blockMap", "RayMarchingDirectAOPass.blockMap")
    g.addEdge("RayMarchingDirectAOPass.color", "ToneMapper.src")
    g.markOutput("ToneMapper.dst")

    log_graph_passes(
        g.name,
        ["VoxelizationPass", "ReadVoxelPass", "RayMarchingDirectAOPass", "ToneMapper"],
    )
    default_framebuffer = resolve_voxel_default_framebuffer(voxel_chain["output_resolution"])
    apply_renderer_overrides(scene_hint, camera_plan, default_framebuffer)
    return g


def create_runtime_execution_graphs(scene_hint, camera_plan, output_mode):
    graphs = {
        "ByObjectRoute": render_graph_hybrid(
            scene_hint,
            camera_plan,
            output_mode,
            graph_name=RUNTIME_GRAPH_NAME_BY_EXECUTION_MODE["ByObjectRoute"],
        ),
        "ForceMeshPipeline": render_graph_force_mesh(
            scene_hint,
            camera_plan,
            graph_name=RUNTIME_GRAPH_NAME_BY_EXECUTION_MODE["ForceMeshPipeline"],
        ),
        "ForceVoxelPipeline": render_graph_force_voxel(
            scene_hint,
            camera_plan,
            graph_name=RUNTIME_GRAPH_NAME_BY_EXECUTION_MODE["ForceVoxelPipeline"],
        ),
    }
    print(
        "[HybridMeshVoxel] runtime graphs:",
        ", ".join(graph.name for graph in graphs.values()),
    )
    print("[HybridMeshVoxel] GUI switch:", "use Mogwai Graphs dropdown to select ByObjectRoute / MeshOnly / VoxelOnly")
    return graphs


def setup_render_graphs():
    set_runtime_resolved_route_source(None)
    scene_hint = resolve_scene_hint()
    camera_plan = resolve_camera_plan(scene_hint)
    output_mode, output_pipeline = resolve_output_mode()
    execution_mode = resolve_execution_mode()

    print("[HybridMeshVoxel] scene hint:", scene_hint if scene_hint else "<empty>")
    print("[HybridMeshVoxel] output mode:", output_mode)
    print("[HybridMeshVoxel] execution mode:", execution_mode)
    if os.environ.get("HYBRID_REFERENCE_VIEW", "").strip():
        print("[HybridMeshVoxel] reference view:", os.environ["HYBRID_REFERENCE_VIEW"].strip())

    if output_pipeline == "mesh":
        if execution_mode != "ByObjectRoute":
            raise RuntimeError("HYBRID_EXECUTION_MODE only applies to hybrid output modes. HYBRID_OUTPUT_MODE=MeshView already selects the dedicated mesh-view graph.")
        graph = render_graph_mesh_view(scene_hint, camera_plan)
        try:
            m.addGraph(graph)
        except NameError:
            pass
        return

    graphs = create_runtime_execution_graphs(scene_hint, camera_plan, output_mode)
    initial_graph = graphs[execution_mode]
    try:
        for graph in graphs.values():
            m.addGraph(graph)
        m.setActiveGraph(initial_graph)
    except NameError:
        pass


setup_render_graphs()
