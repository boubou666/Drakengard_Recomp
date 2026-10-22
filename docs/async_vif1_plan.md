# Plan: VIF1 DMA and VU1 on their own thread

Shared PS2Recomp runtime (`boubou666/PS2Recomp`, `main`). Proposed by the Drakengard session, to be
implemented there and reviewed and tested on Valkyrie Profile 2 by the VP2 session.

## Why

Today a guest store that starts DMA channel 1 (VIF1) does all the work inside that store, on the EE
thread: it walks the tag chain, runs every VIF command, runs each VU1 microprogram to completion, and
pushes PATH1/PATH2/PATH3 through the GIF arbiter. On real hardware VIF1, VU1 and the GIF run alongside
the EE, which keeps executing game code.

Measured in Drakengard's first mission (temporary `PS2X_DMA_STATS` counters, ~11.8 fps):

| per 5 s of play | value |
|---|---|
| VIF1 kicks (ch1) | ~175 (3 per frame) |
| host time inside those kicks (VIF + VU1 + GIF submit) | ~2.7 s, 53% of wall time |
| host time from a kick's end to the game's next poll of ch1 (CHCR or VIF1_STAT) | ~1.6 s (~9 ms per kick) |
| D_STAT reads / DMAC interrupts waited on | none: the game polls CHCR and, twice per frame, VIF1_STAT and GIF_STAT |
| GIF ch2 kicks / VIF0 ch0 kicks | ~240 / ~2600 (VU0 jobs, short) |

If each kick runs on a worker thread, the ~9 ms the EE spends before polling overlaps the ~15 ms of
VIF1/VU1 work: about 30% off the frame time, roughly 11.8 -> 16 fps, until the GS workers (about 75%
busy now) become the limit. VP2 should gain in the field and the movie, where VU1 also dominates.

## Today (summary of the code read)

- `PS2Memory::writeIORegister` (CHCR with STR) snapshots chain-mode data into `chainBuf`, then
  `processPendingTransfers` runs GIF (PATH3), VIF0 and VIF1 in order, drains the GIF arbiter, sets D_STAT
  CIS, clears STR/QWC and queues the DMAC cause. Normal-mode transfers read RDRAM live.
- VIF1 `MSCAL/MSCNT/MSCALF` call back into `PS2Runtime`, which runs `m_vu1` to completion
  (`kVu1ProgramCycleLimit`); `XGKICK` reaches the GS through `submitGifPacket(Path1, drain=true)`.
- The EE always sees "done": STR is cleared on CHCR reads, VIF1_STAT VPS/FQC and VPU_STAT VBS1 read 0,
  `sceGsSyncPath` / `sceDmaSync` (HLE) return at once. DMAC handlers are dispatched from `Store32` via
  `drainCompletedDmacHandlers`.
- Other entry points: `kickGifDmaChainFromMMIO` (recompiler-emitted GIF kicks, with native fast paths),
  HLE `submitDmaSend`, direct stores to VIF1_FIFO, SPR DMA (ch8/9) into VU memory.
- Locks: only the DMAC cause queue and the GS frontend's queues. `m_ioRegisters` (an unordered_map) and
  `vif1_regs` are unlocked.
- Already asynchronous: the GS frontend thread; its cross-thread interrupt path (`postEvent(GsInterrupt)`)
  is the model for DMAC completions from another thread.

## Design

1. **One "VIF1/GIF worker" thread, one ordered job queue.** A job is a channel 1 or channel 2 transfer
   whose data is snapshotted at kick time (chain mode already does this; normal mode copies `qwc * 16`
   bytes), plus anything the worker needs from the EE at kick time (FBRST D/T enables, D_CTRL). Channel
   2 (PATH3) and the MMIO/HLE GIF kicks go through the same queue, so PATH1/2/3 keep today's program order
   (VP2's movie uploads rely on it). VIF0/VU0 stay synchronous on the EE thread (short jobs, COP2 macro
   mode shares VU0).
2. **The worker owns** `m_vu1`, `vif1_regs`, the GIF arbiter and PATH3 masking while jobs run; the EE
   touches them only when the worker is idle. The worker never writes `m_ioRegisters`: per-channel
   "jobs in flight" counters and completion bits are atomics, merged into register reads on the EE.
3. **Completion.** When a job finishes, the worker clears its channel's in-flight count, ORs the D_STAT CIS
   bit into an atomic, queues the cause and posts a scheduler event (as GS interrupts do), so DMAC
   handlers run on the executor at its next checkpoint. The worker only posts: it never calls
   executor-only scheduler code (`checkpointDue`, `accountCycles`, the dispatcher-transfer flag).
   The VU1 recorder (`PS2X_VU1_RECORD`) runs on the worker with start PC, TOP and ITOP taken from the
   job, not from live EE state.
4. **EE-side sync points: wait for the worker to finish what is queued, then proceed as today.**
   - CHCR reads of ch1/ch2 while that channel has jobs in flight: wait for that channel, then return idle
     (the game would spin until then anyway; a host wait costs no CPU and keeps the meaning).
   - VIF1_STAT, GIF_STAT reads; VIF1 register reads/writes (FBRST, MARK, ERR); VPU_STAT reads (COP2
     `cfc2` of VI29): wait for all.
   - D_STAT reads do **not** wait: CIS1/CIS2 come from the worker's atomics and are set only once the
     job is done, as on hardware. (VP2's field polls D_STAT constantly for its synchronous scratchpad
     chains, CIS8/CIS9; waiting there would throw the overlap away.)
   - Any EE load or store to VU1 code/data memory, SPR DMA (ch8/9) touching VU memory, stores to
     VIF1_FIFO: wait for all. VP2's music job reads results at 0x1100E000 right after the kick.
   - GS: EE-side GS register access and the frontend's `waitForIdle` paths (CSR FINISH/SIGNAL, clears,
     local-to-host reads) first wait for the worker, then for the GS queue.
   - HLE `sceGsSyncPath`, `sceDmaSync`, `submitDmaSend`: wait for all.
   - A second kick of a channel whose previous job is still queued is allowed (it queues behind it);
     the games observed poll before re-kicking anyway.
5. **Switch.** `PS2X_VIF1_ASYNC=1` turns it on. It stays off by default until both games pass long runs
   (VP2's field crash fixed in 2b5592d was timing dependent); tests and tools stay synchronous.
6. **Diagnostics.** Keep the kick/slack counters (`PS2X_DMA_STATS`) to measure the overlap actually won.

## Risks

- Hidden reliance on "already done": anything reading VIF1/VU1/GIF state without going through one of
  the sync points above sees stale state. The sync list must be complete; unknown MMIO in the VIF/GIF/VU
  ranges should default to "wait for all".
- Normal-mode DMA reading RDRAM the EE rewrites before polling: snapshotting at kick keeps today's
  semantics.
- DMAC handlers now run later than the kick (at the next checkpoint), as on hardware. Code that relied on
  them running inside the store could change behaviour.
- Determinism: VU1 and EE no longer interleave the same way run to run (the GS was already async).
- `m_ioRegisters` is read from other threads today (debug panel); the worker must not add writers.

## Validation

- Unit tests: kick -> CHCR busy until done; ordering of PATH1/2/3 between the worker and EE-side GS
  writes; VU1 memory reads after a kick see the results; DMAC handler dispatch; sync/async parity of
  VRAM for a scripted frame.
- Drakengard: shadow GS check into the first mission, VU1 trace record/replay (recorder on the worker),
  mission fps and `PS2X_DMA_STATS` overlap.
- VP2 (VP2 session): boot/decryption, title, opening movie (PATH3 order), music (VU1 results read back;
  dropouts or noise are audible at once), 600 s field run, sync/async VU1 trace comparison on its field
  and music trace.
- SPR DMA (`tryProcessScratchpadDma`): wait for the worker only when the source or destination is the
  VU window (the `mapVuMemory` branch); RAM <-> SPR transfers stay as they are.

## Phases

1. Worker + queue for ch1 only, sync points, completion events, opt-in switch; tests. (Drakengard session)
2. Channel 2 and the MMIO/HLE GIF kicks into the same queue; GS sync points. (Drakengard session)
3. VP2 checks; fixes from both sides. (VP2 session, then both)
4. Measurements, then decide the default.
