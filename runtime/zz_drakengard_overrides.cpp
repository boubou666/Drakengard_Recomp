#include "game_overrides.h"
#include "ps2_runtime.h"
#include "ps2_stubs.h"
#include "ps2_syscalls.h"
#include "Stubs/Pad.h"
#include "ps2_recompiled_functions.h"

#include <chrono>
#include <cstdlib>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

// Drakengard (Europe) SLES-52322 build-specific bindings.
namespace
{
    // Wrap a raw handler so it returns to $ra when the handler leaves pc untouched.
    template <void (*Handler)(uint8_t *, R5900Context *, PS2Runtime *)>
    void returningHandler(uint8_t *rdram, R5900Context *ctx, PS2Runtime *runtime)
    {
        const uint32_t entryPc = ctx->pc;
        Handler(rdram, ctx, runtime);
        if (ctx->pc == entryPc)
        {
            ctx->pc = getRegU32(ctx, 31);
        }
    }

    // Test harness for unattended runs: PS2X_INPUT_SCRIPT="sec:mask:dur;..." holds the pad buttons in
    // `mask` (hex, active-high, Start=0008 Cross=4000 Circle=2000 Up=0010 Down=0040) for `dur` seconds,
    // starting `sec` seconds after boot.
    void startInputScriptFromEnvironment()
    {
        const char *script = std::getenv("PS2X_INPUT_SCRIPT");
        if (!script || !*script)
            return;

        struct Step
        {
            double start = 0.0;
            uint16_t mask = 0u;
            double duration = 0.2;
        };
        std::vector<Step> steps;
        std::stringstream entries(script);
        std::string entry;
        while (std::getline(entries, entry, ';'))
        {
            Step step;
            char sep1 = 0, sep2 = 0;
            unsigned mask = 0u;
            std::stringstream fields(entry);
            if (fields >> step.start >> sep1 >> std::hex >> mask >> std::dec >> sep2 >> step.duration &&
                sep1 == ':' && sep2 == ':')
            {
                step.mask = static_cast<uint16_t>(mask);
                steps.push_back(step);
            }
        }

        std::thread([steps]()
                    {
                        const auto boot = std::chrono::steady_clock::now();
                        for (const Step &step : steps)
                        {
                            std::this_thread::sleep_until(boot + std::chrono::duration<double>(step.start));
                            ps2_stubs::setPadOverrideState(static_cast<uint16_t>(~step.mask), 0x80, 0x80, 0x80, 0x80);
                            std::fprintf(stderr, "[input-script] t=%.1fs press mask=0x%04x\n", step.start, step.mask);
                            std::this_thread::sleep_for(std::chrono::duration<double>(step.duration));
                            ps2_stubs::clearPadOverrideState();
                        } })
            .detach();
    }

    // PS2X_FPS_LOG=1: count game frames (the main loop resets its VSync gate at 0x2800D4 once per frame).
    void countedFrameGateReset(uint8_t *rdram, R5900Context *ctx, PS2Runtime *runtime)
    {
        static uint32_t frames = 0u;
        static auto windowStart = std::chrono::steady_clock::now();
        ++frames;
        const auto now = std::chrono::steady_clock::now();
        const double elapsed = std::chrono::duration<double>(now - windowStart).count();
        if (elapsed >= 5.0)
        {
            std::fprintf(stderr, "[fps] game frames/s=%.1f\n", frames / elapsed);
            frames = 0u;
            windowStart = now;
        }
        FUN_002800d4_0x2800d4(rdram, ctx, runtime);
    }

    void applyDrakengardEuOverrides(PS2Runtime &runtime)
    {
        if (const char *fpsLog = std::getenv("PS2X_FPS_LOG"); fpsLog && *fpsLog == '1')
            runtime.registerFunction(0x002800D4u, &countedFrameGateReset);
        // sceCdLayerSearchFile(file, name, layer): same contract as sceCdSearchFile, layer ignored.
        runtime.registerFunction(0x0030A418u, &returningHandler<ps2_stubs::sceCdSearchFile>);

        startInputScriptFromEnvironment();
    }
}

PS2_REGISTER_GAME_OVERRIDE(
    "drakengard-eu",
    "SLES_523.22",
    0x00120008u,
    0u,
    applyDrakengardEuOverrides);
