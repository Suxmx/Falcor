#include "Shading.slang"

ByteAddressBuffer solidVoxelBlockData;
StructuredBuffer<PrimitiveBSDF> gBuffer;
StructuredBuffer<uint> resolvedRouteBuffer;
RWTexture2D<uint4> routeBlockMapMesh;
RWTexture2D<uint4> routeBlockMapVoxel;

cbuffer CB
{
    uint solidVoxelCount;
    uint2 blockCount;
    uint resolvedRouteCount;
    float identityConfidenceThreshold;
}

static const uint kResolvedRouteMesh = 0u;
static const uint kResolvedRouteVoxel = 1u;
static const uint kResolvedRouteNeedsBoth = 2u;

uint2 loadSolidVoxelBlock(uint voxelOffset)
{
    return solidVoxelBlockData.Load2(voxelOffset * 8u);
}

void writeBlockBit(RWTexture2D<uint4> blockMap, uint linearBlockIndex, uint blockZ)
{
    if (linearBlockIndex == 0xffffffffu || blockZ == 0xffffffffu)
        return;

    const uint2 blockXY = uint2(linearBlockIndex % blockCount.x, linearBlockIndex / blockCount.x);
    const uint component = blockZ >> 5u;
    const uint bitMask = 1u << (blockZ & 31u);

    switch (component)
    {
    case 0u:
        InterlockedOr(blockMap[blockXY].x, bitMask);
        break;
    case 1u:
        InterlockedOr(blockMap[blockXY].y, bitMask);
        break;
    case 2u:
        InterlockedOr(blockMap[blockXY].z, bitMask);
        break;
    case 3u:
        InterlockedOr(blockMap[blockXY].w, bitMask);
        break;
    default:
        break;
    }
}

[numthreads(256, 1, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    const uint voxelOffset = dispatchThreadID.x;
    if (voxelOffset >= solidVoxelCount)
        return;

    const PrimitiveBSDF bsdf = gBuffer[voxelOffset];
    if (bsdf.area <= 0.f)
        return;

    const uint2 blockInfo = loadSolidVoxelBlock(voxelOffset);

    bool writeMesh = true;
    bool writeVoxel = true;

    const bool hasTrustedIdentity =
        bsdf.dominantInstanceID != kInvalidVoxelInstanceID &&
        bsdf.dominantInstanceID < resolvedRouteCount &&
        bsdf.identityConfidence >= identityConfidenceThreshold;

    if (hasTrustedIdentity)
    {
        const uint resolvedRoute = resolvedRouteBuffer[bsdf.dominantInstanceID];
        switch (resolvedRoute)
        {
        case kResolvedRouteMesh:
            writeVoxel = false;
            break;
        case kResolvedRouteVoxel:
            writeMesh = false;
            break;
        case kResolvedRouteNeedsBoth:
        default:
            break;
        }
    }

    if (writeMesh)
        writeBlockBit(routeBlockMapMesh, blockInfo.x, blockInfo.y);

    if (writeVoxel)
        writeBlockBit(routeBlockMapVoxel, blockInfo.x, blockInfo.y);
}
