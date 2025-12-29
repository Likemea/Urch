# Urch/functions/code.py
import ast, io, multiprocessing, time, psutil
from contextlib import redirect_stdout

BLACKLISTED_KEYWORDS = ["input", "eval", "exec", "open", "os.system", "subprocess", "shutil", "exit"]

def is_code_safe(code: str) -> bool:
    return not any(bad in code for bad in BLACKLISTED_KEYWORDS)

def execute_sandboxed(code: str, queue, timeout=5, memory_limit_mb=256):
    """Execute code in a sandboxed process with timeout and memory limits"""
    try:
        # Parse syntax first
        ast.parse(code)
        
        # Set up output capture
        f = io.StringIO()
        with redirect_stdout(f):
            # Execute with restricted builtins
            safe_builtins = {
                'print': print,
                'len': len,
                'range': range,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'bool': bool,
                'type': type,
            }
            exec(code, {"__builtins__": safe_builtins})
        
        output = f.getvalue().strip()
        formatted = f"\n```py\n{code}\n```\n"
        if output:
            formatted += f"**Output:**\n```\n{output}\n```"
        else:
            formatted += "**Output:** *(None)*"
        
        queue.put(("success", formatted))
        
    except SyntaxError as e:
        queue.put(("error", f"**Syntax Error:**\n```\n{str(e)}\n```"))
    except Exception as e:
        queue.put(("error", f"**Executed Code:**\n```py\n{code}\n```\n**Error:**\n```\n{str(e)}\n```"))

def monitor_process(process, queue, timeout, memory_limit_mb):
    """Monitor process for time and memory limits"""
    start_time = time.time()
    process_pid = process.pid
    
    while process.is_alive():
        # Check time limit
        if time.time() - start_time > timeout:
            process.terminate()
            queue.put(("error", "⏰ Time limit exceeded (5 seconds)"))
            return
            
        # Check memory limit on Windows
        try:
            proc = psutil.Process(process_pid)
            memory_info = proc.memory_info()
            if memory_info.rss > memory_limit_mb * 1024 * 1024:  # Convert MB to bytes
                process.terminate()
                queue.put(("error", "💾 Memory limit exceeded (256 MiB)"))
                return
        except (psutil.NoSuchProcess, ProcessLookupError):
            # Process already terminated
            break
            
        time.sleep(0.1)  # Check every 100ms

def run_python(code: str) -> str:
    if not is_code_safe(code):
        return "⚠️ Unsafe code detected. Execution blocked."

    # Use multiprocessing for isolation
    ctx = multiprocessing.get_context('spawn')
    queue = ctx.Queue()
    process = ctx.Process(target=execute_sandboxed, args=(code, queue, 5, 256))
    
    try:
        process.start()
        
        # Monitor the process for resource limits
        monitor_process(process, queue, timeout=5, memory_limit_mb=256)
        
        # Wait a bit for clean termination
        process.join(timeout=1)
        
        if process.is_alive():
            process.terminate()
            process.join(timeout=0.5)
            if process.is_alive():
                process.kill()
            return "❌ Process terminated - exceeded resource limits"
        
        # Get result if available
        if not queue.empty():
            result_type, result = queue.get(block=False)
            return result
        else:
            return "❌ Execution failed - no output received"
            
    except Exception as e:
        return f"❌ Sandbox error: {str(e)}"
    finally:
        # Ensure process cleanup
        try:
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
        except:
            pass