import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import time
import psutil
import cProfile
import pstats
import io
import os

# non-interactive backend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

class DiagnoseCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="diagnose", description="Run a lightweight performance profile of the bot's health")
    @app_commands.describe(duration="Duration of diagnostics in seconds (1-60)")
    async def diagnose(self, interaction: discord.Interaction, duration: int = 10):
        if not 1 <= duration <= 60:
            await interaction.response.send_message("Duration must be between 1 and 60 seconds.", ephemeral=True)
            return

        await interaction.response.defer()
        
        cpu_history = []
        latency_history = []
        ram_history = []
        timestamps = []
        
        start_time = time.perf_counter()
        
        profiler = cProfile.Profile()
        profiler.enable()
        
        check_interval = 0.5
        
        psutil.cpu_percent(interval=None)
        
        try:
            while (time.perf_counter() - start_time) < duration:
                loop_start = time.perf_counter()
                await asyncio.sleep(check_interval)
                loop_end = time.perf_counter()
                
                actual_sleep = loop_end - loop_start
                drift = actual_sleep - check_interval
                
                cpu = psutil.cpu_percent(interval=None)
                process = psutil.Process()
                ram = process.memory_info().rss / (1024 * 1024)
                
                cpu_history.append(cpu)
                latency_history.append(drift * 1000)
                ram_history.append(ram)
                timestamps.append(time.perf_counter() - start_time)
                
        except Exception as e:
            print(f"Diagnostics collection error: {e}")
        finally:
            profiler.disable()

        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(15)
        profile_text = s.getvalue()
        
        avg_cpu = sum(cpu_history) / len(cpu_history) if cpu_history else 0
        max_cpu = max(cpu_history) if cpu_history else 0
        avg_latency = sum(latency_history) / len(latency_history) if latency_history else 0
        max_latency = max(latency_history) if latency_history else 0
        avg_ram = sum(ram_history) / len(ram_history) if ram_history else 0
        
        buf = None
        try:
            plt.style.use('dark_background')
            fig, ax1 = plt.subplots(figsize=(10, 5))
            
            color_cpu = '#ff7f0e'
            ax1.set_xlabel('Time (s)')
            ax1.set_ylabel('CPU Usage (%)', color=color_cpu)
            ax1.plot(timestamps, cpu_history, color=color_cpu, label='CPU Usage %', linewidth=2, marker='o', markersize=3)
            ax1.tick_params(axis='y', labelcolor=color_cpu)
            ax1.set_ylim(0, max(100, max_cpu * 1.2))
            ax1.grid(True, alpha=0.2)
            
            ax2 = ax1.twinx()
            color_lat = '#1f77b4'
            ax2.set_ylabel('Loop Latency (ms)', color=color_lat)
            ax2.plot(timestamps, latency_history, color=color_lat, label='Loop Latency ms', linewidth=2, linestyle='--', marker='x', markersize=3)
            ax2.tick_params(axis='y', labelcolor=color_lat)
            ax2.set_ylim(0, max(500, max_latency * 1.5))
            
            plt.title(f'Urch Performance Diagnostic ({duration}s Window)')
            fig.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=120)
            buf.seek(0)
            
            plt.close(fig)
            plt.clf()
        except Exception as e:
            print(f"Diagnostics plotting error: {e}")
            if buf: buf.close()
            buf = None

        embed = discord.Embed(
            title="📊 Urch Performance Diagnostic",
            description=f"Diagnostic window: **{duration}s**",
            color=discord.Color.gold() if max_latency > 100 else discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="💻 CPU Usage", value=f"Avg: `{avg_cpu:.1f}%`\nMax: `{max_cpu:.1f}%`", inline=True)
        embed.add_field(name="🧠 RAM (RSS)", value=f"Avg: `{avg_ram:.1f} MB`\nEnd: `{ram_history[-1]:.1f} MB`", inline=True)
        embed.add_field(name="⌛ Loop Latency", value=f"Avg: `{avg_latency:.1f}ms`\nMax: `{max_latency:.1f}ms`", inline=True)
        embed.add_field(name="📡 Heartbeat", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        
        clean_profile = profile_text.replace(os.getcwd(), ".").strip()
        if len(clean_profile) > 1000:
            clean_profile = clean_profile[:997] + "..."
            
        embed.add_field(name="🔝 Top Bottlenecks (Cumulative Time)", value=f"```\n{clean_profile}\n```", inline=False)
        
        footer_text = "Status: Healthy" if max_latency < 50 else "Status: Loop Blockage Detected" if max_latency > 200 else "Status: Minor Latency Spikes"
        embed.set_footer(text=footer_text)
        
        if buf:
            file = discord.File(buf, filename="diagnostic.png")
            embed.set_image(url="attachment://diagnostic.png")
            await interaction.followup.send(embed=embed, file=file)
            buf.close()
        else:
            await interaction.followup.send(embed=embed, content="⚠️ Failed to generate plot, but metrics are above.")

async def setup(bot):
    await bot.add_cog(DiagnoseCommand(bot))
