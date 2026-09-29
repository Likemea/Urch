# Urch/functions/code_interpreter.py
"""
Ephemeral Sandboxed Code Execution using Bubblewrap (bwrap) and Systemd Cgroups.
Provides process, network, host filesystem isolation, and concurrency queuing
with strict CPU (50% single-core), wall-clock (6s), physical RAM (100MB), task-count
and output-size limits.
"""

import asyncio
import io
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid

import discord

logger = logging.getLogger(__name__)

EXECUTION_TIMEOUT = 6.0

MAX_CONCURRENT_SANDBOXES = 2
_sandbox_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SANDBOXES)

REQUIRE_CGROUP_LIMITS = True

OUTPUT_CAP_BYTES = 1024 * 1024
STDOUT_CHARS = 1100  # discord 2K char limit
STDERR_CHARS = 600

MAX_ATTACHMENTS = 10
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024

_INFRA_ERROR_PREFIXES = ("Failed to connect to", "Failed to start transient", "bwrap:")

ALLOWED_EXTENSIONS = (
    # archives, code
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".c",
    ".cs",
    ".go",
    ".rs",
    ".sh",
    # web, configs
    ".html",
    ".css",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    # docs, data
    ".txt",
    ".md",
    ".log",
    ".csv",
    ".xlsx",
    ".pdf",
    # media
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".m4a",
    ".mp4",
    ".webm",
)


def _which(name: str) -> str | None:
    return shutil.which(name, path=f"{os.environ.get('PATH', '')}:/usr/local/bin:/usr/bin:/bin")


def _launcher_env() -> dict[str, str]:
    """
    Minimal environment for systemd-run/bwrap: none of the bot's secrets,
    plus what `systemd-run --user` needs to find the user bus when PM2 was started by a system
    service rather than from a login session.
    """
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}",
    }
    if bus := os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        env["DBUS_SESSION_BUS_ADDRESS"] = bus
    return env


def _bwrap_command(bwrap_path: str, scratch_dir: str) -> list[str]:
    python_bin = sys.executable
    venv_dir = sys.prefix

    cmd = [
        bwrap_path,
        "--unshare-all",
        "--unshare-user",
        "--die-with-parent",
        "--new-session",
        "--disable-userns",
        "--clearenv",
    ]

    sandbox_env = {
        "PATH": f"{venv_dir}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/tmp",
        "PYTHONPATH": "/workspace",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": "/tmp",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
    }
    for key, value in sandbox_env.items():
        cmd += ["--setenv", key, value]

    read_only_paths = [
        "/usr",
        "/lib",
        "/lib64",
        "/bin",
        "/sbin",
        "/etc/alternatives",
        "/etc/ld.so.cache",
        "/etc/ssl",
        "/etc/ca-certificates",
        "/usr/share/fonts",
        "/etc/fonts",
    ]
    if venv_dir != "/usr":
        read_only_paths.append(venv_dir)
    for path in read_only_paths:
        if os.path.exists(path):
            cmd += ["--ro-bind", path, path]

    cmd += [
        "--tmpfs",
        "/tmp",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--bind",
        scratch_dir,
        "/workspace",
        "--chdir",
        "/workspace",
        python_bin,
        "/workspace/script.py",
    ]
    return cmd


def _systemd_prefix(systemd_run: str, scope_name: str) -> list[str]:
    """Wrap Bubblewrap with Systemd Cgroups v2 Resource Enforcement."""
    return [
        systemd_run,
        "--user",
        "--scope",
        "--quiet",
        "--collect",
        f"--unit={scope_name}",
        "-p",
        "MemoryMax=100M",
        "-p",
        "MemoryHigh=75M",
        "-p",
        "MemorySwapMax=0",
        "-p",
        "CPUQuota=50%",
        "-p",
        "TasksMax=64",
    ]


async def _drain(stream: asyncio.StreamReader, buf: bytearray, proc) -> bool:
    """
    Read a stream into `buf`, never holding more than OUTPUT_CAP_BYTES. Returns True (and kills
    the sandbox) if the script flooded past the cap. The cgroup limits cover the sandbox, not the
    bot's own buffers, so unbounded communicate() could exhaust the VM from the bot's side.
    """
    flooded = False
    while chunk := await stream.read(16384):
        if flooded:
            continue
        room = OUTPUT_CAP_BYTES - len(buf)
        if len(chunk) > room:
            buf += chunk[:room]
            flooded = True
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        else:
            buf += chunk
    return flooded


async def _reap(proc) -> None:
    """
    Wait for the launcher to exit. asyncio's Process.wait() only resolves once the stdout/stderr
    pipes hit EOF, and a paused, undrained pipe never does, so keep draining while waiting.
    """

    async def swallow(stream: asyncio.StreamReader) -> None:
        while await stream.read(65536):
            pass

    try:
        await asyncio.wait_for(
            asyncio.gather(swallow(proc.stdout), swallow(proc.stderr), proc.wait()),
            timeout=5,
        )
    except asyncio.TimeoutError:
        logger.warning("Sandbox launcher did not exit within 5s of SIGKILL")


async def _hard_kill(proc, scope_name: str | None, env: dict[str, str]) -> None:
    """SIGKILL everything in the sandbox's cgroup scope, then the launcher, and reap it."""
    systemctl = _which("systemctl")
    if scope_name and systemctl:
        try:
            killer = await asyncio.create_subprocess_exec(
                systemctl,
                "--user",
                "kill",
                "--signal=SIGKILL",
                f"{scope_name}.scope",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
            await asyncio.wait_for(killer.wait(), timeout=3)
        except (OSError, asyncio.TimeoutError):
            pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    await _reap(proc)


def _collect_files(scratch_dir: str) -> list[tuple[str, bytes]]:
    """
    Read back files the script produced, including those in subdirectories.

    The scratch dir is attacker-controlled and this code runs OUTSIDE the sandbox: a symlink
    named `x.txt` pointing at the bot's `.env` would otherwise be read and uploaded.
    O_NOFOLLOW + fstat on the opened descriptor makes that impossible.
    """
    collected: list[tuple[str, bytes]] = []
    total = 0

    for root, _dirs, names in os.walk(scratch_dir):
        for name in sorted(names):
            if len(collected) >= MAX_ATTACHMENTS:
                return collected

            full_path = os.path.join(root, name)
            rel_name = os.path.relpath(full_path, scratch_dir)

            if rel_name == "script.py" or not rel_name.lower().endswith(ALLOWED_EXTENSIONS):
                continue

            fd = None
            try:
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
                fd = os.open(full_path, flags)
                st = os.fstat(fd)
                if not stat.S_ISREG(st.st_mode):
                    continue
                if st.st_size == 0 or st.st_size > MAX_FILE_BYTES:
                    continue
                if total + st.st_size > MAX_TOTAL_BYTES:
                    continue
                with os.fdopen(fd, "rb") as f:
                    fd = None
                    data = f.read(st.st_size)
            except OSError:
                continue
            finally:
                if fd is not None:
                    os.close(fd)

            safe_name = rel_name.replace(os.sep, "__")
            collected.append((safe_name, data))
            total += len(data)

    return collected


def _write_script(scratch_dir: str, code: str) -> None:
    with open(os.path.join(scratch_dir, "script.py"), "w", encoding="utf-8", errors="replace") as f:
        f.write(code)


def _remove_tree(path: str) -> None:
    """rmtree that survives a script chmod-ing its own directories shut (which would leak them)."""
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    for root, dirs, _files in os.walk(path):
        for d in dirs:
            p = os.path.join(root, d)
            if not os.path.islink(p):
                try:
                    os.chmod(p, 0o700)
                except OSError:
                    pass
    shutil.rmtree(path, ignore_errors=True)


def _clean(text: str, limit: int) -> str:
    """Make sandbox output safe to embed in our ``` block, and mark truncation."""
    text = text.replace("```", "`\u200b``")
    if len(text) > limit:
        text = text[:limit] + "\n… (truncated)"
    return text


def _format_streams(raw_out: str, raw_err: str) -> str:
    parts = []
    if raw_out:
        parts.append(f"**Output:**\n```\n{_clean(raw_out, STDOUT_CHARS)}\n```\n")
    if raw_err:
        parts.append(f"**Errors/Warnings:**\n```\n{_clean(raw_err, STDERR_CHARS)}\n```\n")
    return "".join(parts)


async def run_sandboxed_python(code: str) -> tuple[str, list[discord.File]]:
    """
    Executes arbitrary Python code in an isolated Bubblewrap container governed by Systemd Cgroups.
    Queues excess requests via semaphore to prevent memory spikes.
    Returns (stdout_and_stderr_string, list_of_generated_discord_files).

    Callers should also send the result with `allowed_mentions=discord.AllowedMentions.none()`.
    """
    bwrap_path = _which("bwrap")
    if not bwrap_path:
        return "❌ Bubblewrap (`bwrap`) is not available on this system.", []
    systemd_run = _which("systemd-run")
    if not systemd_run and REQUIRE_CGROUP_LIMITS:
        return "❌ Sandbox unavailable: `systemd-run` is required to enforce resource limits.", []

    async with _sandbox_semaphore:
        scratch_dir = None
        scope_name = None
        proc = None
        env = _launcher_env()
        out_buf, err_buf = bytearray(), bytearray()
        flooded = timed_out = False
        files: list[discord.File] = []
        output = ""

        try:
            scratch_dir = tempfile.mkdtemp(prefix="urch_run_")

            await asyncio.to_thread(_write_script, scratch_dir, code)

            cmd = _bwrap_command(bwrap_path, scratch_dir)
            if systemd_run:
                scope_name = f"urch_sandbox_{uuid.uuid4().hex[:8]}"
                cmd = _systemd_prefix(systemd_run, scope_name) + cmd

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                out_flood, err_flood, _ = await asyncio.wait_for(
                    asyncio.gather(
                        _drain(proc.stdout, out_buf, proc),
                        _drain(proc.stderr, err_buf, proc),
                        proc.wait(),
                    ),
                    timeout=EXECUTION_TIMEOUT,
                )
                flooded = out_flood or err_flood
            except asyncio.TimeoutError:
                timed_out = True

            if timed_out or flooded:
                await _hard_kill(proc, scope_name, env)

            raw_out = out_buf.decode("utf-8", errors="replace").strip()
            raw_err = err_buf.decode("utf-8", errors="replace").strip()
            rc = proc.returncode

            launcher_failed = (
                rc == 1 and not raw_out and raw_err.lstrip().startswith(_INFRA_ERROR_PREFIXES)
            )
            if rc != 0 and launcher_failed and not (timed_out or flooded):
                safe_err = re.sub(r"[^\x20-\x7e]", "?", raw_err[:500])
                logger.error("Sandbox launcher failed (rc=%s): %s", rc, safe_err)
                return "[Sandbox]: ❌ The sandbox is unavailable right now.", []

            if timed_out:
                note = f"[Sandbox]: ⏰ Execution timed out (max {EXECUTION_TIMEOUT}s).\n"
            elif flooded:
                note = "[Sandbox]: 🌊 Output limit exceeded, execution stopped.\n"
            elif rc in (-9, 137):
                note = "[Sandbox]: 💥 Process killed.\n"
            elif rc != 0 and not raw_err:
                note = f"[Sandbox]: Exited with code {rc}.\n"
            else:
                note = ""

            output = (note + _format_streams(raw_out, raw_err)) or "No output"

            if not (timed_out or flooded):
                collected = await asyncio.to_thread(_collect_files, scratch_dir)
                files = [discord.File(fp=io.BytesIO(data), filename=n) for n, data in collected]

        except Exception:
            logger.exception("Sandbox execution failed")
            output, files = "[Sandbox]: ❌ Internal error while running the sandbox.", []
        finally:
            if proc is not None and proc.returncode is None:
                await _hard_kill(proc, scope_name, env)
            if scratch_dir:
                await asyncio.to_thread(_remove_tree, scratch_dir)

        return output, files
