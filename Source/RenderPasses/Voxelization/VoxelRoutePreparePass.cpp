#include "VoxelRoutePreparePass.h"
#include "Shading.slang"
#include "RenderGraph/RenderPassStandardFlags.h"
#include <algorithm>
#include <vector>

namespace
{
const std::string kShaderFile = "RenderPasses/Voxelization/VoxelRoutePrepare.cs.slang";
const std::string kPropIdentityConfidenceThreshold = "identityConfidenceThreshold";
}

VoxelRoutePreparePass::VoxelRoutePreparePass(ref<Device> pDevice, const Properties& props)
    : RenderPass(pDevice), mpDevice(pDevice), gridData(VoxelizationBase::GlobalGridData)
{
    parseProperties(props);
}

void VoxelRoutePreparePass::parseProperties(const Properties& props)
{
    for (const auto& [key, value] : props)
    {
        if (key == kPropIdentityConfidenceThreshold)
            mIdentityConfidenceThreshold = std::clamp(float(value), 0.0f, 1.0f);
        else
            logWarning("Unknown property '{}' in VoxelRoutePreparePass properties.", key);
    }
}

Properties VoxelRoutePreparePass::getProperties() const
{
    Properties props;
    props[kPropIdentityConfidenceThreshold] = mIdentityConfidenceThreshold;
    return props;
}

RenderPassReflection VoxelRoutePreparePass::reflect(const CompileData& compileData)
{
    RenderPassReflection reflector;

    reflector.addInput(kGBuffer, kGBuffer)
        .bindFlags(ResourceBindFlags::ShaderResource)
        .format(ResourceFormat::Unknown)
        .rawBuffer(static_cast<uint32_t>(gridData.solidVoxelCount * sizeof(PrimitiveBSDF)));

    reflector.addInput(kSolidVoxelBlockData, kSolidVoxelBlockData)
        .bindFlags(ResourceBindFlags::ShaderResource)
        .format(ResourceFormat::Unknown)
        .rawBuffer(static_cast<uint32_t>(gridData.solidVoxelCount * sizeof(uint32_t) * 2u));

    reflector.addOutput(kRouteBlockMapMesh, kRouteBlockMapMesh)
        .bindFlags(ResourceBindFlags::ShaderResource | ResourceBindFlags::UnorderedAccess)
        .format(ResourceFormat::RGBA32Uint)
        .texture2D(gridData.blockCount().x, gridData.blockCount().y);

    reflector.addOutput(kRouteBlockMapVoxel, kRouteBlockMapVoxel)
        .bindFlags(ResourceBindFlags::ShaderResource | ResourceBindFlags::UnorderedAccess)
        .format(ResourceFormat::RGBA32Uint)
        .texture2D(gridData.blockCount().x, gridData.blockCount().y);

    return reflector;
}

void VoxelRoutePreparePass::execute(RenderContext* pRenderContext, const RenderData& renderData)
{
    auto& dict = renderData.getDictionary();
    if (mOptionsChanged)
    {
        auto flags = dict.getValue(kRenderPassRefreshFlags, RenderPassRefreshFlags::None);
        dict[Falcor::kRenderPassRefreshFlags] = flags | Falcor::RenderPassRefreshFlags::RenderOptionsChanged;
        mOptionsChanged = false;
    }

    ref<Texture> pRouteBlockMapMesh = renderData.getTexture(kRouteBlockMapMesh);
    ref<Texture> pRouteBlockMapVoxel = renderData.getTexture(kRouteBlockMapVoxel);
    pRenderContext->clearUAV(pRouteBlockMapMesh->getUAV().get(), uint4(0));
    pRenderContext->clearUAV(pRouteBlockMapVoxel->getUAV().get(), uint4(0));

    if (!mpScene || gridData.solidVoxelCount == 0)
        return;

    updateResolvedRouteBuffer();

    if (!mpPreparePass)
    {
        ProgramDesc desc;
        desc.addShaderLibrary(kShaderFile).csEntry("main");
        mpPreparePass = ComputePass::create(mpDevice, desc, DefineList(), true);
    }

    ShaderVar var = mpPreparePass->getRootVar();
    var[kGBuffer] = renderData.getResource(kGBuffer)->asBuffer();
    var[kSolidVoxelBlockData] = renderData.getResource(kSolidVoxelBlockData)->asBuffer();
    var["resolvedRouteBuffer"] = mpResolvedRouteBuffer;
    var[kRouteBlockMapMesh] = pRouteBlockMapMesh;
    var[kRouteBlockMapVoxel] = pRouteBlockMapVoxel;

    auto cb = var["CB"];
    cb["solidVoxelCount"] = static_cast<uint32_t>(gridData.solidVoxelCount);
    cb["blockCount"] = gridData.blockCount();
    cb["resolvedRouteCount"] = mResolvedRouteCount;
    cb["identityConfidenceThreshold"] = mIdentityConfidenceThreshold;

    mpPreparePass->execute(pRenderContext, uint3(static_cast<uint32_t>(gridData.solidVoxelCount), 1, 1));
}

void VoxelRoutePreparePass::compile(RenderContext* pRenderContext, const CompileData& compileData) {}

void VoxelRoutePreparePass::renderUI(Gui::Widgets& widget)
{
    if (widget.slider("Identity Threshold", mIdentityConfidenceThreshold, 0.0f, 1.0f))
        mOptionsChanged = true;
}

void VoxelRoutePreparePass::setScene(RenderContext* pRenderContext, const ref<Scene>& pScene)
{
    mpScene = pScene;
    mResolvedRouteCount = 0;
    mpResolvedRouteBuffer = nullptr;
}

void VoxelRoutePreparePass::updateResolvedRouteBuffer()
{
    if (!mpScene)
    {
        mResolvedRouteCount = 0;
        return;
    }

    const uint32_t instanceCount = mpScene->getGeometryInstanceCount();
    mResolvedRouteCount = instanceCount;

    const uint32_t bufferElementCount = std::max(instanceCount, 1u);
    if (!mpResolvedRouteBuffer || mpResolvedRouteBuffer->getElementCount() < bufferElementCount)
    {
        mpResolvedRouteBuffer = mpDevice->createStructuredBuffer(
            sizeof(uint32_t),
            bufferElementCount,
            ResourceBindFlags::ShaderResource,
            MemoryType::DeviceLocal,
            nullptr,
            false
        );
    }

    std::vector<uint32_t> resolvedRoutes(bufferElementCount, static_cast<uint32_t>(Scene::GeometryInstanceResolvedRoute::NeedsBoth));
    for (uint32_t instanceID = 0; instanceID < instanceCount; ++instanceID)
        resolvedRoutes[instanceID] = static_cast<uint32_t>(mpScene->getGeometryInstanceResolvedRoute(instanceID));

    mpResolvedRouteBuffer->setBlob(resolvedRoutes.data(), 0, bufferElementCount * sizeof(uint32_t));
}
