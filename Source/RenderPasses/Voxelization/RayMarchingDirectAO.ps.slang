#ifndef CHECK_ELLIPSOID
#define CHECK_ELLIPSOID 1
#endif

#ifndef CHECK_VISIBILITY
#define CHECK_VISIBILITY 1
#endif

#ifndef CHECK_COVERAGE
#define CHECK_COVERAGE 1
#endif

#ifndef USE_MIP_MAP
#define USE_MIP_MAP 1
#endif

#ifndef USE_ENV_MAP
#define USE_ENV_MAP 0
#endif

#include "Voxel/VoxelGrid.slang"
#include "Math/VoxelizationUtility.slang"
#include "Shading.slang"
import Scene.Scene;
import Scene.SceneTypes;

Texture3D<int> vBuffer;
StructuredBuffer<PrimitiveBSDF> gBuffer;
StructuredBuffer<Ellipsoid> pBuffer;
Texture2D<uint4> blockMap;
Texture2D<uint4> routeBlockMapMesh;
Texture2D<uint4> routeBlockMapVoxel;
StructuredBuffer<uint> resolvedRouteBuffer;

cbuffer GridData
{
    float3 gridMin;
    float3 voxelSize;
    uint3 voxelCount;
    uint solidVoxelCount;
}

cbuffer CB
{
    uint2 pixelCount;
    float4x4 invVP;
    float shadowBias;
    uint drawMode;
    uint instanceRouteMask;
    bool useResolvedExecutionRoutes;
    uint resolvedRouteCount;
    float resolvedRouteConfidenceThreshold;
    bool renderBackground;
    float transmittanceThreshold;
    bool aoEnabled;
    float aoStrength;
    float aoRadius;
    uint aoStepCount;
    uint aoDirectionSet;
    float aoContactStrength;
    bool aoUseStableRotation;
}

#include "RayMarchingTraversal.slang"

struct PsOut
{
    float4 color : SV_Target0;
    float voxelDepth : SV_Target1;
    float4 voxelNormal : SV_Target2;
    float voxelConfidence : SV_Target3;
    uint voxelInstanceID : SV_Target4;
};

static const uint kDrawModeCombined = 0;
static const uint kDrawModeDirectOnly = 1;
static const uint kDrawModeAOOnly = 2;
static const uint kDrawModeNormalDebug = 3;
static const uint kDrawModeCoverageDebug = 4;
static const uint kAllInstanceRouteMask = 0x7u;
static const uint kRouteMaskBlend = 1u << uint(GeometryInstanceRenderRoute::Blend);
static const uint kRouteMaskMeshOnly = 1u << uint(GeometryInstanceRenderRoute::MeshOnly);
static const uint kRouteMaskVoxelOnly = 1u << uint(GeometryInstanceRenderRoute::VoxelOnly);

#define MAX_ANALYTIC_LIGHTS 8

uint hashCell(int3 cellInt)
{
    uint seed = asuint(cellInt.x) * 73856093u;
    seed ^= asuint(cellInt.y) * 19349663u;
    seed ^= asuint(cellInt.z) * 83492791u;
    seed ^= seed >> 16;
    seed *= 2246822519u;
    seed ^= seed >> 13;
    seed *= 3266489917u;
    seed ^= seed >> 16;
    return seed;
}

float hashToUnitFloat(uint seed)
{
    return float(seed) * (1.0f / 4294967295.0f);
}

void buildShadingBasis(float3 mainNormal, out float3 tangent, out float3 bitangent)
{
    float3 up = abs(mainNormal.z) < 0.999f ? float3(0, 0, 1) : float3(0, 1, 0);
    tangent = normalizeSafe(cross(up, mainNormal));
    if (dot(tangent, tangent) < 1e-6f)
        tangent = float3(1, 0, 0);
    bitangent = normalizeSafe(cross(mainNormal, tangent));
}

void applyStableRotation(inout float3 tangent, inout float3 bitangent, float angle)
{
    float s = sin(angle);
    float c = cos(angle);
    float3 rotatedTangent = c * tangent + s * bitangent;
    float3 rotatedBitangent = c * bitangent - s * tangent;
    tangent = rotatedTangent;
    bitangent = rotatedBitangent;
}

float evalProbeOcclusion(float3 origin, float3 direction, float maxDistance)
{
    const uint stepCount = max(aoStepCount, 1u);
    const float safeRadius = max(maxDistance, 1e-3f);
    const float stepLength = safeRadius / float(stepCount);
    float occlusion = 0.0f;

    [loop]
    for (uint stepIndex = 1; stepIndex <= stepCount; ++stepIndex)
    {
        float probeDistance = stepLength * float(stepIndex);
        HitResult probe = rayMarching(origin, direction, probeDistance, true);
        if (probe.hit)
        {
            float distanceWeight = 1.0f - (float(stepIndex) - 1.0f) / float(stepCount);
            occlusion = saturate(distanceWeight);
            break;
        }
    }

    return occlusion;
}

float evalContactAO(HitResult hit, float3 mainNormal, float3 tangent, float3 bitangent)
{
    const float3 origin = hit.cell + shadowBias * mainNormal;
    const float contactRadius = clamp(aoRadius * 0.35f, 1.0f, 2.5f);
    float occlusion = 0.0f;

    [unroll]
    for (uint sampleIndex = 0; sampleIndex < 4; ++sampleIndex)
    {
        float azimuth = (float(sampleIndex) + 0.5f) * (Pi * 0.5f);
        float3 lateral = cos(azimuth) * tangent + sin(azimuth) * bitangent;
        float3 probeDir = normalizeSafe(mainNormal * 1.15f + lateral);
        if (dot(probeDir, probeDir) > 0.0f)
            occlusion += rayMarching(origin, probeDir, contactRadius, true).hit ? 1.0f : 0.0f;
    }

    float meanOcclusion = occlusion * 0.25f;
    return saturate(1.0f - aoContactStrength * meanOcclusion);
}

float evalMacroAO(HitResult hit, float3 mainNormal, float3 tangent, float3 bitangent)
{
    const uint directionCount = aoDirectionSet >= 6 ? 6u : 4u;
    const float3 origin = hit.cell + shadowBias * mainNormal;
    float occlusion = 0.0f;

    [loop]
    for (uint sampleIndex = 0; sampleIndex < directionCount; ++sampleIndex)
    {
        float azimuth = (2.0f * Pi) * (float(sampleIndex) + 0.5f) / float(directionCount);
        float3 lateral = cos(azimuth) * tangent + sin(azimuth) * bitangent;
        float3 probeDir = normalizeSafe(mainNormal * 1.35f + 0.75f * lateral);
        occlusion += evalProbeOcclusion(origin, probeDir, aoRadius);
    }

    return saturate(1.0f - occlusion / float(directionCount));
}

float evalStableAO(HitResult hit, float3 mainNormal)
{
    if (!aoEnabled || aoStrength <= 0.0f || aoRadius <= 0.0f)
        return 1.0f;

    float3 tangent;
    float3 bitangent;
    buildShadingBasis(mainNormal, tangent, bitangent);

    if (aoUseStableRotation)
    {
        float stableAngle = (2.0f * Pi) * hashToUnitFloat(hashCell(hit.cellInt));
        applyStableRotation(tangent, bitangent, stableAngle);
    }

    float contactAO = evalContactAO(hit, mainNormal, tangent, bitangent);
    float macroAO = evalMacroAO(hit, mainNormal, tangent, bitangent);
    return lerp(1.0f, contactAO * macroAO, saturate(aoStrength));
}

float3 screenCoordToCell(float2 screenCoord, float ndcDepth)
{
    float4 ndc = float4(2 * screenCoord.x - 1, 1 - 2 * screenCoord.y, ndcDepth, 1);
    float4 temp = mul(invVP, ndc);
    float4 posWorld = temp / temp.w;
    return (posWorld.xyz - gridMin) / voxelSize;
}

float4 renderMissBackground(float3 direction)
{
#if USE_ENV_MAP
    if (renderBackground)
        return float4(gScene.envMap.eval(direction), 1);
#endif

    if (!renderBackground)
        return float4(0, 0, 0, 1);

    float t = saturate(direction.y * 0.5f + 0.5f);
    float3 horizonColor = float3(0.08f, 0.09f, 0.11f);
    float3 zenithColor = float3(0.26f, 0.29f, 0.35f);
    float3 color = lerp(horizonColor, zenithColor, t);
    return float4(color, 1);
}

float evalVoxelDepth(float3 posW)
{
    return length(posW - gScene.camera.getPosition());
}

// 确定性直接光照：遍历所有 analytic 光源，无随机采样
// 若场景无 analytic 光，返回简单 ambient 使画面可见
float3 evalDeterministicDirectLighting(HitResult hit, uint offset, float3 viewDir)
{
    PrimitiveBSDF bsdf = gBuffer[offset];
    bsdf.updateCoverage(viewDir, transmittanceThreshold);

    float3 posW = gridMin + hit.cell * voxelSize;

    float3 result = 0;
    uint lightCount = min(gScene.getLightCount(), (uint)MAX_ANALYTIC_LIGHTS);
    uint supportedLightCount = 0;
    for (uint i = 0; i < lightCount; i++)
    {
        LightData light = gScene.getLight(i);
        float3 lightDir = 0;
        float3 lightColor = 0;
        float lightDistance = -1;

        if (light.type == LightType::Point)
        {
            float3 toL = light.posW - posW;
            lightDistance = length(toL);
            lightDir = toL / max(lightDistance, 1e-6f);

            float sqrDist = max(dot(toL, toL), 1e-4f);
            float spot = 1.0f;
            if (light.openingAngle < Pi)
            {
                float cosTerm = dot(light.dirW, -lightDir);
                float cosOuter = light.cosOpeningAngle;
                float innerAng = max(light.openingAngle - light.penumbraAngle, 0.0f);
                float cosInner = cos(innerAng);
                float t2 = saturate((cosTerm - cosOuter) / max(cosInner - cosOuter, 1e-6f));
                spot = t2 * t2 * (3.0f - 2.0f * t2);
                if (light.penumbraAngle <= 0.0f)
                    spot = (cosTerm >= cosOuter) ? 1.0f : 0.0f;
            }
            lightColor = light.intensity * spot / sqrDist;
        }
        else if (light.type == LightType::Directional)
        {
            lightDir = -light.dirW;
            lightColor = light.intensity;
            lightDistance = -1;
        }
        else
        {
            continue;
        }

        supportedLightCount++;

        // 距离转换为体素单位（visibility 函数用体素坐标距离）
        float3 shadowNormal = bsdf.surface.getMainNormal(lightDir);
        float voxelDist = lightDistance > 0 ? lightDistance / voxelSize.x : -1;
        float visibility = calcLightVisibility(hit, lightDir, shadowNormal, voxelDist);
        if (visibility <= 0)
            continue;

        float3 h = normalizeSafe(lightDir + viewDir);
        result += visibility * lightColor * bsdf.eval(lightDir, viewDir, h);
    }

    bool hasStableDirectTerm = supportedLightCount > 0;

#if USE_ENV_MAP
    float3 envDir = bsdf.surface.getMainNormal(viewDir);
    float3 envColor = gScene.envMap.eval(envDir);
    if (any(envColor > 0))
    {
        float3 envH = normalizeSafe(envDir + viewDir);
        result += envColor * bsdf.eval(envDir, viewDir, envH);
        hasStableDirectTerm = true;
    }
#endif

    // 没有 analytic light，且没有 env map 时，保留最弱的 fallback，避免画面全黑
    if (!hasStableDirectTerm)
    {
        float3 skyDir = normalize(float3(0.3f, 1.0f, 0.2f));
        float3 ambientNormal = bsdf.surface.getMainNormal(skyDir);
        float NdotL = saturate(dot(ambientNormal, skyDir));
        float ambient = 0.05f;
        float3 h2 = normalizeSafe(skyDir + viewDir);
        result = (NdotL + ambient) * bsdf.eval(skyDir, viewDir, h2);
    }

    return result;
}

PsOut main(float2 texCoord : TEXCOORD, float4 pos : SV_POSITION)
{
    PsOut psOut = {};

    float3 from = screenCoordToCell(texCoord, 0);
    float3 to = screenCoordToCell(texCoord, 1);
    float3 delta = to - from;
    float3 direction = normalizeSafe(delta);
    psOut.color = renderMissBackground(direction);
    psOut.voxelDepth = 0.f;
    psOut.voxelNormal = float4(0.f, 0.f, 0.f, 0.f);
    psOut.voxelConfidence = 0.f;
    psOut.voxelInstanceID = kInvalidVoxelInstanceID;

    if (all(direction == 0))
        return psOut;

    float2 inOut = clip(float3(0), float3(voxelCount), from, to);
    if (inOut.x < 0)
        return psOut;

    from += (inOut.x + 1e-6f) * delta;
    HitResult hit = rayMarching(from, direction, -1, false);
#if CHECK_ELLIPSOID
    if (!hit.hit)
        hit = rayMarchingConservative(from, direction, false);
#endif
    if (!hit.hit)
        return psOut;

    uint offset = vBuffer[hit.cellInt];
    PrimitiveBSDF bsdf = gBuffer[offset];
    float3 viewDir = -direction;
    float3 mainNormal = bsdf.surface.getMainNormal(viewDir);
    float coverage = bsdf.calcCoverage(viewDir);
    float ao = evalStableAO(hit, mainNormal);
    float3 posW = gridMin + hit.cell * voxelSize;
    float3 color = 0;

    psOut.voxelDepth = evalVoxelDepth(posW);
    psOut.voxelNormal = float4(mainNormal, 1.f);
    psOut.voxelConfidence = saturate(bsdf.identityConfidence);
    psOut.voxelInstanceID = bsdf.dominantInstanceID;

    switch (drawMode)
    {
    case kDrawModeNormalDebug:
        color = mainNormal * 0.5f + 0.5f;
        break;
    case kDrawModeCoverageDebug:
        color = valueToColor(coverage);
        break;
    case kDrawModeDirectOnly:
        color = evalDeterministicDirectLighting(hit, offset, viewDir);
        break;
    case kDrawModeCombined:
        color = evalDeterministicDirectLighting(hit, offset, viewDir) * ao;
        break;
    case kDrawModeAOOnly:
        color = pow(saturate(ao), 12.0f).xxx;
        break;
    default:
        color = float3(0.2f, 0.7f, 0.2f);
        break;
    }

    psOut.color = float4(color, 1);
    return psOut;
}
