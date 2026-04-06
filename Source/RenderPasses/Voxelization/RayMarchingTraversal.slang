struct HitResult
{
    bool hit;
    int3 cellInt;
    float3 cell;
};

uint getGeometryInstanceRenderRouteBit(GeometryInstanceRenderRoute route)
{
    return 1u << uint(route);
}

uint getGeometryInstanceResolvedRouteBit(uint resolvedRoute)
{
    switch (resolvedRoute)
    {
    case 0u:
        return kRouteMaskMeshOnly;
    case 1u:
        return kRouteMaskVoxelOnly;
    case 2u:
    default:
        return kRouteMaskBlend;
    }
}

uint4 loadActiveBlockMap(uint2 blockXY)
{
    if (!useResolvedExecutionRoutes || instanceRouteMask == kAllInstanceRouteMask)
        return blockMap[blockXY];

    const bool wantsMeshResolved = (instanceRouteMask & kRouteMaskMeshOnly) != 0u;
    const bool wantsVoxelResolved = (instanceRouteMask & kRouteMaskVoxelOnly) != 0u;

    if (wantsMeshResolved && !wantsVoxelResolved)
        return routeBlockMapMesh[blockXY];

    if (wantsVoxelResolved && !wantsMeshResolved)
        return routeBlockMapVoxel[blockXY];

    return blockMap[blockXY];
}

bool isAcceptedVoxelOffset(int offset)
{
    PrimitiveBSDF bsdf = gBuffer[offset];
    if (bsdf.area <= 0)
        return false;

    if (instanceRouteMask == kAllInstanceRouteMask)
        return true;

    if (!useResolvedExecutionRoutes)
    {
        if (bsdf.identityConfidence <= 0.f || bsdf.dominantInstanceID == kInvalidVoxelInstanceID)
            return true;

        GeometryInstanceID instanceID = { bsdf.dominantInstanceID };
        const GeometryInstanceRenderRoute route = gScene.getGeometryInstanceRenderRoute(instanceID);
        return (instanceRouteMask & getGeometryInstanceRenderRouteBit(route)) != 0u;
    }

    if (
        resolvedRouteCount == 0u || bsdf.identityConfidence < resolvedRouteConfidenceThreshold || bsdf.dominantInstanceID == kInvalidVoxelInstanceID ||
        bsdf.dominantInstanceID >= resolvedRouteCount
    )
        return true;

    const uint resolvedRoute = resolvedRouteBuffer[bsdf.dominantInstanceID];
    return (instanceRouteMask & getGeometryInstanceResolvedRouteBit(resolvedRoute)) != 0u;
}

bool isSolidVoxel(int3 cellInt, out int offset)
{
    offset = vBuffer[cellInt];
    if (offset < 0 || offset >= solidVoxelCount)
        return false;
    return gBuffer[offset].area > 0;
}

bool isSolidBlock(int3 blockInt)
{
    int component = blockInt.z / 32;
    uint value = 1 << blockInt.z % 32;
    uint4 zMap = loadActiveBlockMap(blockInt.xy);
    switch (component)
    {
    case 0:
        value &= zMap.x;
        break;
    case 1:
        value &= zMap.y;
        break;
    case 2:
        value &= zMap.z;
        break;
    case 3:
        value &= zMap.w;
        break;
    }
    return value != 0;
}

// 先后用体素和椭球裁剪线段
HitResult checkPrimitive(Ellipsoid ellipsoid, float3 cell, float3 direction, int3 cellInt)
{
    float3 from = cell - cellInt;
    int3 directions = int3(sign(direction));
    float3 border = (directions + 1) / 2;
    float3 t = (border - from) / direction;
    float tMin = 2.0f;
    if (direction.x != 0 && t.x < tMin)
        tMin = t.x;
    if (direction.y != 0 && t.y < tMin)
        tMin = t.y;
    if (direction.z != 0 && t.z < tMin)
        tMin = t.z;
    float3 to = from + tMin * direction;
    float2 inOut = ellipsoid.clip(from, to);
    HitResult result = { inOut.x >= 0, cellInt, cell + inOut.x * (to - from) };
    return result;
}

// 统一用网格坐标表示
HitResult rayMarching_DDA(float3 from, float3 direction, bool ignoreFirst)
{
    float3 cell = from;
    int3 cellInt = int3(floor(from));

    float3 reciprocal_direction = 1.0f / direction;
    // 可选的前进方向
    int3 directions = int3(sign(direction));
    if (ignoreFirst)
        leave(cell, cellInt, directions, direction, reciprocal_direction);

    while (true)
    {
        if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
            break;
        int offset;
        if (isSolidVoxel(cellInt, offset) && isAcceptedVoxelOffset(offset))
        {
#if !CHECK_ELLIPSOID
            HitResult hit = { true, cellInt, cellInt + 0.5f };
            return hit;
#else
            Ellipsoid ellipsoid = pBuffer[offset];
            HitResult hit = checkPrimitive(ellipsoid, cell, direction, cellInt);
            if (hit.hit)
                return hit;
#endif
        }
        leave(cell, cellInt, directions, direction, reciprocal_direction);
    }
    HitResult hit = { false, cellInt, cellInt + 0.5f };
    return hit;
}

// 统一用网格坐标表示
HitResult rayMarching_DDA(float3 from, float3 direction, float maxDistance, bool ignoreFirst)
{
    float3 cell = from;
    int3 cellInt = int3(floor(from));
    float distance = 0;

    float3 reciprocal_direction = 1.0f / direction;
    // 可选的前进方向
    int3 directions = int3(sign(direction));
    if (ignoreFirst)
        distance += leave(cell, cellInt, directions, direction, reciprocal_direction);

    while (true)
    {
        if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
            break;
        if (maxDistance > 0 && distance > maxDistance) // 非正数表示不限制距离
            break;
        int offset;
        if (isSolidVoxel(cellInt, offset) && isAcceptedVoxelOffset(offset))
        {
#if !CHECK_ELLIPSOID
            HitResult hit = { true, cellInt, cellInt + 0.5f };
            return hit;
#else
            Ellipsoid ellipsoid = pBuffer[offset];
            HitResult hit = checkPrimitive(ellipsoid, cell, direction, cellInt);
            if (hit.hit)
                return hit;
#endif
        }
        distance += leave(cell, cellInt, directions, direction, reciprocal_direction);
    }
    HitResult hit = { false, cellInt, cellInt + 0.5f };
    return hit;
}

HitResult rayMarching_Mipmap(float3 from, float3 direction, bool ignoreFirst)
{
    float3 cell = from;
    int3 cellInt = int3(floor(from));

    float3 reciprocal_direction = 1.0f / direction;
    // 可选的前进方向
    int3 directions = int3(sign(direction));
    if (ignoreFirst)
        leave(cell, cellInt, directions, direction, reciprocal_direction);

    while (true)
    {
        if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
            break;

        int3 blockInt = cellInt / BLOCK_TO_VOXEL;
        if (isSolidBlock(blockInt))
        {
            int3 current = blockInt;
            while (all(current == blockInt))
            {
                if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
                    break;
                int offset;
                if (isSolidVoxel(cellInt, offset) && isAcceptedVoxelOffset(offset))
                {
#if !CHECK_ELLIPSOID
                    HitResult hit = { true, cellInt, cellInt + 0.5f };
                    return hit;
#else
                    Ellipsoid ellipsoid = pBuffer[offset];
                    HitResult hit = checkPrimitive(ellipsoid, cell, direction, cellInt);
                    if (hit.hit)
                        return hit;
#endif
                }
                leave(cell, cellInt, directions, direction, reciprocal_direction);
                current = cellInt / BLOCK_TO_VOXEL;
            }
        }
        else
        {
            leaveBlock(cell, cellInt, directions, direction, reciprocal_direction);
        }
    }
    HitResult hit = { false, cellInt, cellInt + 0.5f };
    return hit;
}

HitResult rayMarching_Mipmap(float3 from, float3 direction, float maxDistance, bool ignoreFirst)
{
    float3 cell = from;
    int3 cellInt = int3(floor(from));
    float distance = 0;

    float3 reciprocal_direction = 1.0f / direction;
    // 可选的前进方向
    int3 directions = int3(sign(direction));
    if (ignoreFirst)
        distance += leave(cell, cellInt, directions, direction, reciprocal_direction);

    while (true)
    {
        if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
            break;
        if (distance > maxDistance) // 非正数表示不限制距离
            break;

        int3 blockInt = cellInt / BLOCK_TO_VOXEL;
        if (isSolidBlock(blockInt))
        {
            int3 current = blockInt;
            while (all(current == blockInt))
            {
                if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
                    break;
                if (distance > maxDistance) // 非正数表示不限制距离
                    break;
                int offset;
                if (isSolidVoxel(cellInt, offset) && isAcceptedVoxelOffset(offset))
                {
#if !CHECK_ELLIPSOID
                    HitResult hit = { true, cellInt, cellInt + 0.5f };
                    return hit;
#else
                    Ellipsoid ellipsoid = pBuffer[offset];
                    HitResult hit = checkPrimitive(ellipsoid, cell, direction, cellInt);
                    if (hit.hit)
                        return hit;
#endif
                }
                distance += leave(cell, cellInt, directions, direction, reciprocal_direction);
                current = cellInt / BLOCK_TO_VOXEL;
            }
        }
        else
        {
            distance += leaveBlock(cell, cellInt, directions, direction, reciprocal_direction);
        }
    }
    HitResult hit = { false, cellInt, cellInt + 0.5f };
    return hit;
}

HitResult rayMarchingConservative_DDA(float3 from, float3 direction, bool ignoreFirst)
{
    float3 cell = from;
    int3 cellInt = int3(floor(from));

    float3 reciprocal_direction = 1.0f / direction;
    int3 directions = int3(sign(direction));
    if (ignoreFirst)
        leave(cell, cellInt, directions, direction, reciprocal_direction);

    while (true)
    {
        if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
            break;

        int offset;
        if (isSolidVoxel(cellInt, offset) && isAcceptedVoxelOffset(offset))
        {
            HitResult hit = { true, cellInt, cellInt + 0.5f };
            return hit;
        }

        leave(cell, cellInt, directions, direction, reciprocal_direction);
    }

    HitResult hit = { false, cellInt, cellInt + 0.5f };
    return hit;
}

HitResult rayMarchingConservative_Mipmap(float3 from, float3 direction, bool ignoreFirst)
{
    float3 cell = from;
    int3 cellInt = int3(floor(from));

    float3 reciprocal_direction = 1.0f / direction;
    int3 directions = int3(sign(direction));
    if (ignoreFirst)
        leave(cell, cellInt, directions, direction, reciprocal_direction);

    while (true)
    {
        if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
            break;

        int3 blockInt = cellInt / BLOCK_TO_VOXEL;
        if (isSolidBlock(blockInt))
        {
            int3 current = blockInt;
            while (all(current == blockInt))
            {
                if (any(cellInt < int3(0)) || any(cellInt >= (int3)voxelCount))
                    break;

                int offset;
                if (isSolidVoxel(cellInt, offset) && isAcceptedVoxelOffset(offset))
                {
                    HitResult hit = { true, cellInt, cellInt + 0.5f };
                    return hit;
                }

                leave(cell, cellInt, directions, direction, reciprocal_direction);
                current = cellInt / BLOCK_TO_VOXEL;
            }
        }
        else
        {
            leaveBlock(cell, cellInt, directions, direction, reciprocal_direction);
        }
    }

    HitResult hit = { false, cellInt, cellInt + 0.5f };
    return hit;
}

HitResult rayMarching(float3 from, float3 direction, float maxDistance, bool ignoreFirst)
{
    direction = normalizeSafe(direction);
    if (all(direction == float3(0)))
    {
        HitResult hit = { false, int3(from), from };
        return hit;
    }
#if USE_MIP_MAP
    if (maxDistance > 0)
        return rayMarching_Mipmap(from, direction, maxDistance, ignoreFirst);
    return rayMarching_Mipmap(from, direction, ignoreFirst);
#else
    if (maxDistance > 0)
        return rayMarching_DDA(from, direction, maxDistance, ignoreFirst);
    return rayMarching_DDA(from, direction, maxDistance, ignoreFirst);
#endif
}

HitResult rayMarchingConservative(float3 from, float3 direction, bool ignoreFirst)
{
    direction = normalizeSafe(direction);
    if (all(direction == float3(0)))
    {
        HitResult hit = { false, int3(from), from };
        return hit;
    }

#if USE_MIP_MAP
    return rayMarchingConservative_Mipmap(from, direction, ignoreFirst);
#else
    return rayMarchingConservative_DDA(from, direction, ignoreFirst);
#endif
}

float calcLightVisibility(HitResult hit, float3 direction, float3 mainNormal, float distance)
{
    float ignoreDistance = 2; // 忽略光源附近的体素
    if (distance >= 0 && distance <= ignoreDistance)
        return 1;
    float3 from = hit.cell + shadowBias * mainNormal;
    hit = rayMarching(from, direction, distance - ignoreDistance, true);
    return hit.hit ? 0 : 1;
}
