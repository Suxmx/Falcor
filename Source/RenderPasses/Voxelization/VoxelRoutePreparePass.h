#pragma once

#include "VoxelizationBase.h"

using namespace Falcor;

class VoxelRoutePreparePass : public RenderPass
{
public:
    FALCOR_PLUGIN_CLASS(VoxelRoutePreparePass, "VoxelRoutePreparePass", "Prepare route-aware voxel block maps for hybrid execution.");

    static ref<VoxelRoutePreparePass> create(ref<Device> pDevice, const Properties& props)
    {
        return make_ref<VoxelRoutePreparePass>(pDevice, props);
    }

    VoxelRoutePreparePass(ref<Device> pDevice, const Properties& props);

    virtual Properties getProperties() const override;
    virtual RenderPassReflection reflect(const CompileData& compileData) override;
    virtual void execute(RenderContext* pRenderContext, const RenderData& renderData) override;
    virtual void compile(RenderContext* pRenderContext, const CompileData& compileData) override;
    virtual void renderUI(Gui::Widgets& widget) override;
    virtual void setScene(RenderContext* pRenderContext, const ref<Scene>& pScene) override;

private:
    void parseProperties(const Properties& props);
    void updateResolvedRouteBuffer();

    ref<Device> mpDevice;
    ref<Scene> mpScene;
    ref<ComputePass> mpPreparePass;
    ref<Buffer> mpResolvedRouteBuffer;

    GridData& gridData;
    float mIdentityConfidenceThreshold = 0.95f;
    bool mOptionsChanged = false;
    uint32_t mResolvedRouteCount = 0;
};
