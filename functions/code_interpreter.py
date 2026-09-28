# Urch/functions/code_interpreter.py
"""
Ephemeral Sandboxed Code Execution using Bubblewrap (bwrap).
Provides process, network, and host filesystem isolation with strict
CPU (5s), wall-clock (6s), and memory (100MB) constraints.
"""

import asyncio
import io
import os
import shutil
import sys
import tempfile
import uuid
import discord

try:
    import resource
except ImportError:
    resource = None

MAX_MEMORY_BYTES = 100 * 1024 * 1024
EXECUTION_TIMEOUT = 6.0
ALLOWED_EXTENSIONS = (
    # archives, code
    ".zip", ".tar", ".gz", ".7z",
    ".py", ".js", ".ts", ".java", ".cpp", ".c", ".cs", ".go", ".rs", ".sh",
    
    # web, configs
    ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".toml",
    
    # docs, data
    ".txt", ".md", ".log", ".csv", ".xlsx", ".pdf",
    
    # media
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a",
    ".mp4", ".webm"
)              

def _set_limits():
    """Enforces CPU and memory limits on the sandboxed child process."""
    if resource is not None:
        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 6))

async def run_sandboxed_python(code: str) -> tuple[str, list[discord.File]]:
    """
    Executes arbitrary Python code in an isolated Bubblewrap container.
    Returns (stdout_and_stderr_string, list_of_generated_discord_files).
    """
    scratch_dir = os.path.join(tempfile.gettempdir(), f"urch_run_{uuid.uuid4().hex[:8]}")
    os.makedirs(scratch_dir, exist_ok=True)

    injected_code = (
        "import sys, os\n"
        "os.environ['MPLCONFIGDIR'] = '/tmp'\n"
        "try:\n"
        "    import matplotlib\n"
        "    matplotlib.use('Agg')\n"
        "except ImportError: pass\n\n"
        f"{code}\n"
    )

    script_path = os.path.join(scratch_dir, "script.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(injected_code)

    python_bin = sys.executable
    venv_dir = sys.prefix

    bwrap_path = shutil.which("bwrap") or "/usr/bin/bwrap"

    bwrap_cmd = [
        bwrap_path,
        "--unshare-all",
        "--unshare-net",
        "--die-with-parent",
        "--new-session",
        "--disable-userns",
        "--clearenv",
        
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/etc", "/etc",
        
        "--setenv", "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "--setenv", "HOME", "/tmp",
        "--setenv", "PYTHONPATH", "/workspace",
        "--setenv", "OPENBLAS_NUM_THREADS", "1",
        "--setenv", "OMP_NUM_THREADS", "1",
        "--setenv", "MPLCONFIGDIR", "/tmp",
]

    for path in ["/lib64", "/bin", "/etc/alternatives", "/etc/ld.so.cache"]:
        if os.path.exists(path):
            bwrap_cmd.extend(["--ro-bind", path, path])

    if venv_dir != "/usr" and os.path.exists(venv_dir):
        bwrap_cmd.extend(["--ro-bind", venv_dir, venv_dir])

    bwrap_cmd.extend([
        "--tmpfs", "/tmp",
        "--proc", "/proc",
        "--dev", "/dev",
        "--bind", scratch_dir, "/workspace",
        "--chdir", "/workspace",
        python_bin, "/workspace/script.py"
    ])

    files = []
    output = ""
    proc = None

    try:
        if not shutil.which("bwrap") and not os.path.exists("/usr/bin/bwrap"):
            return "❌ Bubblewrap (`bwrap`) is not available on this system.", []

        preexec = _set_limits if (resource is not None and sys.platform != "win32") else None

        proc = await asyncio.create_subprocess_exec(
            *bwrap_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=preexec
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=EXECUTION_TIMEOUT)
        
        raw_out = stdout.decode("utf-8", errors="replace").strip()
        raw_err = stderr.decode("utf-8", errors="replace").strip()

        if raw_out:
            output += f"**Output:**\n```\n{raw_out[:1500]}\n```\n"
        if raw_err:
            output += f"**Errors/Warnings:**\n```\n{raw_err[:800]}\n```\n"
        if not raw_out and not raw_err:
            output = "No output"

        for fname in os.listdir(scratch_dir):
            if fname.lower().endswith(ALLOWED_EXTENSIONS) and fname != "script.py":
                fpath = os.path.join(scratch_dir, fname)
                if os.path.isfile(fpath) and os.path.getsize(fpath) <= 8 * 1024 * 1024:
                    with open(fpath, "rb") as af:
                        buf = io.BytesIO(af.read())
                    buf.seek(0)
                    files.append(discord.File(fp=buf, filename=fname))

    except asyncio.TimeoutError:
        output = f"[Sandbox]: ⏰ Execution timed out (max {EXECUTION_TIMEOUT}s)."
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
    except Exception as e:
        output = f"[Sandbox]: ❌ {str(e)}"
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)

    return output, files