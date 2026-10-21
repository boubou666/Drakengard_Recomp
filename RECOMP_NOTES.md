# Drakengard (EU, SLES-52322) – PS2Recomp bring-up notes

## Layout
- `game/` – full ISO contents (ELF `SLES_523.22`, `MODULES/*.IRX`, `*.BIN` archives). The runtime uses the ELF's folder as `cdrom0:`.
- `PS2Recomp/` – clone of https://github.com/ran-j/PS2Recomp, branch **`drakengard`** (based on upstream eb8688b) holding
  all runtime fixes below. Its generated `src/runner/register_functions.cpp` is left as an uncommitted local change.
- `runtime/zz_drakengard_overrides.cpp` – game-specific override module (source of truth; `scripts/sync_runner.py`
  installs it into the runner).
- `scripts/` – `build_tools.bat` (recompiler/analyzer), `build_runner.bat` (runner, `Fast` config, logs off, `.map`),
  `sync_runner.py` (installs generated code + override into the runner, copying only changed files).
- `tools/ghidra_12.1.4_PUBLIC/` – Ghidra; uses the ghidra-emotionengine-reloaded extension already in `%APPDATA%\ghidra`.
- `recomp/ghidra/` – Ghidra project, headless scripts (`ghidra_run.bat` = import+analyze+export, `ghidra_export.bat` = export only),
  `ghidra_functions.csv` (raw export) and `ghidra_functions_fixed.csv` (5 non-contiguous functions clipped).
- `recomp/drakengard_ghidra.toml` – **current config**: analyzer SDK stubs + Ghidra syscall stubs + Ghidra map +
  extra `entry_points` (unregistered J/JAL targets, gap starts, every data pointer into code).
- `recomp/output_ghidra/` – generated C++ (~40,400 functions) synced into `PS2Recomp/ps2xRuntime/src/runner` + `include`.
- Older heuristic-only attempt: `recomp/drakengard.toml`, `recomp/output/`.

## Rebuild / run
Tools: `PS2Recomp/out/build` (ps2_recomp, ps2_analyzer). Runner: `PS2Recomp/out/build-fast`
(custom `Fast` config, `/O2` without LTCG; the stock Release /LTCG link ran >1h and was abandoned).
A full runner rebuild takes ~40 min (any change to a generated header invalidates the PCH).

    scripts\build_tools.bat                                          # once
    PS2Recomp\out\build\ps2xRecomp\ps2_recomp.exe recomp\drakengard_ghidra.toml
    python scripts\sync_runner.py
    scripts\build_runner.bat
    cd game && ..\PS2Recomp\out\build-fast\ps2xRuntime\ps2EntryRunner.exe D:\Drakengard_Recomp\game\SLES_523.22

Keyboard: arrows = D-pad, X = Cross, C = Circle, Z = Square, V = Triangle, Enter = Start, Q/E = L1/R1. Gamepads work via raylib.

## Fixes applied
Game-specific:
1. `sceCdLayerSearchFile@0x30A418` routed to the runtime's `sceCdSearchFile` (`runtime/zz_drakengard_overrides.cpp`).

Runtime (generic, candidates for upstream):
2. GS interrupt (INTC cause 0) raised on SIGNAL/FINISH 0->1 edges (`g_gsCsrRaisedEdges`, `PS2Runtime::pollGsInterrupt`).
   Drakengard's per-frame texture-upload state machine is driven by it.
3. EE scheduler wall-clock catch-up (`EeScheduler::checkpointDue`): when guest code runs slower than real time
   (busy-wait loops charge few cycles), fast-forward to the next event once its host deadline passes.
   Without it VSync ran at ~1 Hz instead of 60 Hz.
4. Pad HLE: `PAD_MODETABLE` reports digital + DualShock (was digital only), and pressure mode reports `0x79`.
   Drakengard requires both to accept a DUALSHOCK 2.
5. Memory card HLE: first `sceMcGetInfo` after `sceMcInit` reports -1 (card newly detected) like real libmc, and
   `sceMcGetEntSpace` checks the directory (-4 when missing, else free entries in its clusters) instead of a
   hard-coded 1024. The fake 1024 for the missing `/BESLES-52322` contradicted `GetDir` and made the game show
   "no memory card in slot 1". Host-side card folder: `game/mc0`.
6. Display (`gs_cpu_backend.cpp`):
   - Interlaced FRAME mode (`SMODE2` INT=1, FFMD=1, which Drakengard uses) reads only `(DH+1)/2` framebuffer
     lines and line-doubles them. Before, the runtime read all 511 lines and showed the second buffer (fbp 80)
     underneath the picture.
   - Sprite FST texture coordinates keep their 4 fractional bits (were `u >> 4`). Drakengard copies its 480-line
     render into the 256-line display buffer with v starting at 0.5 / 1.5 texels per field; truncation turned
     that into whole-line jumps.
   - `applyFrameModeStabilize`: while consecutive frames differ only slightly (the per-field half-line offset,
     fades), present the average of the newest and previous distinct frame, removing the 1-line vertical
     shimmer on progressive displays; real motion and long-static images are shown unblended.
7. IOP heap (`ps2xIOP/src/emulator/core/iop_memory.cpp`, `services/iop_module_loader.cpp`): the heap window
   (0x120000-0x1F0000) was full when Drakengard asked for its 256 KB movie buffer, while ~800 KB between the
   loaded IRX modules and 0x120000 was never used. Requests that don't fit the window now fall back to a
   first-fit search of that gap (real SysMem serves modules and heap from one pool); the module loader records
   where modules end and refuses to load over heap blocks placed there.

8. EE FPU compares (`ps2xRuntime/include/ps2_runtime_macros.h`): `c.eq/lt/le.s` use PS2 ordering
   (`ps2FpuCompareKey`: no NaN/Inf, exponent 255 is a huge value, denormals = 0). Drakengard seeds a
   nearest-object search with 0x7FFFFFFF ("max float", NaN on the host), so no object was ever linked and a
   comb sort on 0 elements hung forever right after NEW GAME.
9. EE `cvt.w.s` truncates toward zero and saturates (`ps2FpuCvtWS`). It used the host rounding mode, so the
   mission loader's comb sort (`gap = int(gap / 1.3)`) stayed at gap 2 forever.
10. Recompiler: VU0 `vf0` is hard-wired to (0,0,0,1). Macro-mode instructions that write vf0 are followed by a
    restore (`InstructionTranslator::translate`); a clobbered vf0 turned object distances into NaN and left
    mission object groups empty (another infinite comb sort).
11. SPR DMA (`tryProcessScratchpadDma`) accepts MADR in the VU memory window (0x11000000+). Drakengard's VU0
    vertex pipeline copies results out of VU0 data memory (0x11004AE0) with toSPR; that copy was dropped, so
    stale input floats were sent to the GS as vertices (screen-sized garbage triangles, ~1 fps).
12. VU MAX/MINI compare raw sign-magnitude bits and ABS only clears the sign bit (`ps2_vu1_upper.cpp`). They
    flushed denormal operands to 0, and Drakengard's VU1 program `max`es integer vertex colors against 0, so
    every 3D vertex color became black.
13. VIF0 shares VIF1's UNPACK implementation (all formats, masks, MODE, ROW/COL; `executeVifUnpack`) and
    handles MSCAL/MSCALF/MSCNT. It used to unpack only 32-bit formats and stopped at the first unknown VIFcode.

## Performance work (game frames/s: logos 11 -> 30, title/menu 6 -> 30, prologue ~5 -> 20)
Measured with `PS2X_FPS_LOG=1` and the sampling profiler (see harness). The bottleneck was the software GS
rasterizer, which runs on the EE thread:
- Bilinear filtering used `std::lround` (CRT call) x4 per texel -> 8.8 fixed-point blend (`SampleTexture`).
- `ps2_runtime` gets `/Ob2 /Oi /GS-` in the local `Fast` config (generated code stays `/Ob1` to keep builds short).
- Aggressive logs and IOP RPC tracing are off in `out/build-fast` (`build_perf` flags:
  `-DPS2X_ENABLE_AGRESSIVE_LOGS=OFF -DPS2X_ENABLE_IOP_RPC_TRACE=OFF`; runtime logs still on).
- Lazily decoded texel cache per bound texture, invalidated by per-8KiB-page VRAM write generations
  (`GSMem::g_pageWriteGeneration`) and CLUT reloads (`PrepareTexelCache`).
- Large sprites/triangles (>= 2048 px, 16/32-bit frame and Z formats) are rasterized by rows on a worker pool
  (`ForEachRow`, up to 7 workers); texture page cache is per thread. Rasterizer threads defer page-generation
  bumps and each primitive marks its render-target pages once (shared counters were thrashing between cores).
- At a locked 30 fps the game's per-field half-line offset no longer alternates, so the 1-pixel bounce is gone
  on logos/title/menus (`recomp/jitter_check.py` measures it from captures).
Remaining prologue cost is serial: texture uploads to 4/8-bit formats (`UploadImage`/`WriteP4`/`WriteP8`),
small glyph sprites, and IOP kernel scheduling (`IopKernel::beginNextReady`, ~8%).

## Test harness (opt-in, environment variables)
- `PS2X_CAPTURE_DIR=<folder>` (+ `PS2X_CAPTURE_INTERVAL=<sec>`, default 5): the runtime saves the presented
  frame as `frame_<tenths of a second>.png` (`ps2_runtime.cpp`, `UploadFrame`); works minimized/unfocused.
- `PS2X_FPS_LOG=1`: prints game frames/s every 5 s (Drakengard frame-gate counter in `runtime/zz_drakengard_overrides.cpp`).
- `PS2X_PROFILE=<sec>` (+ `PS2X_PROFILE_DELAY`, `PS2X_PROFILE_OUT`): in-process sampling profiler
  (`ps2xRuntime/src/profiling/sampling_profiler.cpp`); symbolize with
  `python recomp/symbolize_profile.py PS2Recomp/out/build-fast/ps2xRuntime/ps2EntryRunner.map <profile>`
  (the `Fast` link writes a `.map`).
- `PS2X_INPUT_SCRIPT="sec:mask:dur;..."`: holds pad buttons (hex, active-high: Start 0008, Cross 4000,
  Circle 2000, Left 0080, Right 0020, Up 0010, Down 0040) `sec` seconds after boot (`runtime/zz_drakengard_overrides.cpp`).
- New game from boot: `115:0008:0.5;125:4000:0.5;136:0080:0.3;140:4000:0.5`, then Cross every ~8 s from 185 s
  (prologue text, "Chapter 1 Verse 2" briefing -> Continue, mission objective/hint dialogs). Mission gameplay
  starts around 270-290 s; timing drifts with machine load, so keep pressing.
- `PS2X_TRACE_CDREAD=1`: logs every sceCdRead. `PS2X_DUMP_EE_THREADS=<sec>`: periodic guest thread dump.
- `PS2X_GS_DUMP_AT=<sec>` (+ `PS2X_GS_DUMP_COUNT`, `PS2X_GS_DUMP_OUT`): writes the next N GS primitives (draw
  state + vertices) and the GIF tags feeding them, tagged with the GIF path and VU1 program (`vu1pc`).
  `recomp/analyze_gs_dump.py` summarizes triangle sizes; `recomp/vudis.py` disassembles VU microcode.

## Current state
Boots through logos, title, main menu, difficulty prompt, prologue text (advance with Cross), "Chapter 1
Beginnings", the Verse 2 briefing, and into the first mission: HUD, radar, objective map, hint and in-mission
dialog ("Lord Caim! The Empire has surrounded the castle!"), with textured, lit 3D geometry (stone pillars).
Known issues / next steps:
- Mission performance ~5 fps. EE thread: ~45% VU1 interpreter (cycle-accurate pipeline model:
  `commitReadyPipelines`, operand normalization, hazard scheduling), ~25% rasterizer. Needs a faster VU1 path.
- The sky band (EE-built REGLIST triangles, texture 12288, z=0) has vertices clamped to 0 and draws ~300
  screen-sized triangles per frame; unclear whether that is accurate. The ground is untextured fog so far, and
  the camera framing (pillars hanging from the top) has not been checked against real hardware.
- Prologue/briefing screens run at ~9 fps; logos/title/menus locked at 30 fps.
- Intro movie: streaming starts after the logos (`sceCdStStart` on MOVIE0EU.BIN) but the MPEG decoder stalls
  (`DemuxPssRing:BACKPRESSURE`) and the game skips to the title.
- Testing tip: bringing the window to the foreground during automated runs registered Enter (Start) presses;
  prefer the in-runtime capture above.
