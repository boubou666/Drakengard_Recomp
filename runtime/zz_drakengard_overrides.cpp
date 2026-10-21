#include "game_overrides.h"
#include "ps2_runtime.h"
#include "ps2_stubs.h"
#include "ps2_syscalls.h"
#include "Stubs/Pad.h"
#include "runtime/ee_scheduler.h"
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

    // PS2X_TRACE_CDREAD=1: log every sceCdRead (sector, count, destination, caller) with a timestamp.
    void tracedCdRead(uint8_t *rdram, R5900Context *ctx, PS2Runtime *runtime)
    {
        static const auto start = std::chrono::steady_clock::now();
        const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        std::fprintf(stderr, "[cdread] t=%.1f lbn=0x%x sectors=%u buf=0x%x ra=0x%x\n", elapsed, getRegU32(ctx, 4),
                     getRegU32(ctx, 5), getRegU32(ctx, 6), getRegU32(ctx, 31));
        FUN_0030b368_0x30b368(rdram, ctx, runtime);
        std::fprintf(stderr, "[cdread]   -> v0=%d\n", static_cast<int32_t>(getRegU32(ctx, 2)));
    }

    // PS2X_DUMP_EE_THREADS=<seconds>: periodically print every guest thread (status, wait reason, pc).
    void startEeThreadDumpFromEnvironment(PS2Runtime &runtime)
    {
        const char *interval = std::getenv("PS2X_DUMP_EE_THREADS");
        const double seconds = interval ? std::atof(interval) : 0.0;
        if (seconds <= 0.0)
            return;
        std::thread([&runtime, seconds]()
                    {
                        const auto start = std::chrono::steady_clock::now();
                        for (;;)
                        {
                            std::this_thread::sleep_for(std::chrono::duration<double>(seconds));
                            const EeKernelSnapshot snapshot = runtime.eeScheduler().snapshot();
                            const double t = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
                            std::fprintf(stderr, "[ee-threads] t=%.0f running=%d\n", t, snapshot.runningThreadId);
                            for (const EeThreadSnapshot &thread : snapshot.threads)
                                std::fprintf(stderr,
                                             "[ee-threads]   id=%d status=%d wait=%d waitId=%d prio=%d/%d pc=0x%x ra=0x%x entry=0x%x wakeups=%u\n",
                                             thread.id, static_cast<int>(thread.status), static_cast<int>(thread.waitReason),
                                             thread.waitId, thread.currentPriority, thread.initialPriority, thread.pc, thread.ra,
                                             thread.entry, thread.wakeupCount);
                            for (const EeSemaphoreSnapshot &sema : snapshot.semaphores)
                                std::fprintf(stderr, "[ee-threads]   sema id=%d count=%d/%d\n", sema.id, sema.count, sema.maxCount);
                        } })
            .detach();
    }

    void applyDrakengardEuOverrides(PS2Runtime &runtime)
    {
        startEeThreadDumpFromEnvironment(runtime);
        if (const char *fpsLog = std::getenv("PS2X_FPS_LOG"); fpsLog && *fpsLog == '1')
            runtime.registerFunction(0x002800D4u, &countedFrameGateReset);
        if (const char *cdTrace = std::getenv("PS2X_TRACE_CDREAD"); cdTrace && *cdTrace == '1')
            runtime.registerFunction(0x0030B368u, &tracedCdRead);
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
