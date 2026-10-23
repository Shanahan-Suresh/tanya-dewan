"""Run one GPU job under the forge-tools GPU lease, with Forge stopped for its length.

    C:\\Python314\\python.exe -u tools\\gpu_run.py --label eval --minutes 60 -- <command> [args...]

The 4B models need about 11 GB of VRAM, and an idle Forge Neo holds about 10 GB, so the job needs
the card to itself. It queues visibly: `forge.lease_acquire` writes a waiter file stating the job's
length (--minutes), the queue on every session's status line shows it, and Forge batches hand the
card over at a frame boundary once it ranks ahead of them (least work left first, with credit for
time waited). Holding the lease, it stops Forge (`-Force`: the lease is this job's), runs the
command, restarts Forge if it stopped it, and releases the lease however the run ends.
Launch it detached with forge-tools `launch-hidden.ps1`, since it can wait for hours.
"""
import argparse
import os
import subprocess
import sys
import threading
import time

FORGE_TOOLS = r"D:\Projects\personal\forge-tools"
sys.path.insert(0, FORGE_TOOLS)
import forge  # noqa: E402
from train_when_idle import PS  # noqa: E402


def forge_up() -> bool:
    try:
        forge._call("/sdapi/v1/progress", timeout=10)
        return True
    except Exception:
        return False


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--minutes", type=float, required=True, help="expected run time; ranks the job in the queue")
    ap.add_argument("--cwd", default=None)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not cmd:
        ap.error("no command given")

    # The waiter's arrival time is the plan start, so its credit for time waited survives each
    # 30-minute lease_acquire call. Its work is stated in frames of the default frame time.
    forge._PLAN_STARTED = time.time()
    work = max(1, round(args.minutes * 60 / forge.DEFAULT_SPF))
    forge._REMAINING = work                      # what lease_beat() reports while the job holds the card
    log(f"queued for the GPU lease: {args.minutes:g} minutes of work")
    held = None
    while held is None:
        held = forge.lease_acquire("parlimen-search " + args.label, remaining=work)
        if held is None:
            log("still queued")
    stop = threading.Event()

    def beat():
        while not stop.wait(30):
            forge.lease_beat()

    threading.Thread(target=beat, daemon=True).start()
    was_up = forge_up()
    try:
        if was_up:
            log("lease held; stopping Forge")
            subprocess.run(PS + [os.path.join(FORGE_TOOLS, "ensure-forge.ps1"), "-Stop", "-Force"],
                           creationflags=forge.NO_WINDOW, check=False)
        log("running:", " ".join(cmd))
        run = subprocess.run(cmd, cwd=args.cwd, check=False)
        log("exited", run.returncode)
        return run.returncode
    finally:
        if was_up:
            # -Force: this run still holds the lease, and ensure-forge.ps1 refuses a start under a holder.
            subprocess.run(PS + [os.path.join(FORGE_TOOLS, "ensure-forge.ps1"), "-Force"],
                           creationflags=forge.NO_WINDOW, check=False)
        stop.set()
        forge._lease_release(held)
        forge._LEASE = None
        log("lease released" + (", Forge restarted" if was_up else ""))


if __name__ == "__main__":
    sys.exit(main())
