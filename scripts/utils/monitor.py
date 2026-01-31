#!/usr/bin/env python3
"""
Luna Engine Real-Time Monitor

Displays live system state, traces, and errors.
Run with: python scripts/monitor.py
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path
from collections import deque

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich import box
except ImportError:
    print("Install rich: pip install rich")
    sys.exit(1)


class LunaMonitor:
    def __init__(self, log_file: str = "/tmp/luna_backend.log"):
        self.console = Console()
        self.log_file = Path(log_file)
        
        # State tracking
        self.requests = deque(maxlen=20)
        self.routes = deque(maxlen=20)
        self.contexts = deque(maxlen=10)
        self.errors = deque(maxlen=20)
        self.history_state = []
        self.last_update = None
        
        # File position for tailing
        self.file_pos = 0
    
    def parse_log_line(self, line: str):
        """Parse a trace log line and update state."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if "[REQUEST]" in line:
            msg = line.split("[REQUEST]")[-1].strip()
            self.requests.append({"time": timestamp, "msg": msg[:60]})
        
        elif "[ROUTE]" in line:
            msg = line.split("[ROUTE]")[-1].strip()
            self.routes.append({"time": timestamp, "msg": msg})
        
        elif "[CONTEXT]" in line:
            msg = line.split("[CONTEXT]")[-1].strip()
            self.contexts.append({"time": timestamp, "msg": msg[:80]})
        
        elif "[STATE]" in line and "History" in line:
            msg = line.split("[STATE]")[-1].strip()
            self.history_state.append(msg)
            self.history_state = self.history_state[-5:]
        
        elif "[ERROR]" in line or "[WARN]" in line or "Error" in line:
            self.errors.append({"time": timestamp, "msg": line[-100:]})
        
        self.last_update = timestamp
    
    def tail_log(self):
        """Read new lines from log file."""
        if not self.log_file.exists():
            return
        
        try:
            with open(self.log_file, 'r') as f:
                f.seek(self.file_pos)
                for line in f:
                    self.parse_log_line(line.strip())
                self.file_pos = f.tell()
        except Exception as e:
            self.errors.append({"time": datetime.now().strftime("%H:%M:%S"), "msg": str(e)})
    
    def make_request_table(self) -> Table:
        """Build requests table."""
        table = Table(title="📥 Recent Requests", box=box.ROUNDED, expand=True)
        table.add_column("Time", style="cyan", width=8)
        table.add_column("Message", style="white")
        
        for req in list(self.requests)[-10:]:
            table.add_row(req["time"], req["msg"])
        
        if not self.requests:
            table.add_row("-", "(waiting for requests)")
        
        return table
    
    def make_route_table(self) -> Table:
        """Build routing decisions table."""
        table = Table(title="🔀 Routing Decisions", box=box.ROUNDED, expand=True)
        table.add_column("Time", style="cyan", width=8)
        table.add_column("Decision", style="white")
        
        for route in list(self.routes)[-10:]:
            style = "green" if "delegated" in route["msg"] else "yellow"
            table.add_row(route["time"], Text(route["msg"], style=style))
        
        if not self.routes:
            table.add_row("-", "(no routing yet)")
        
        return table
    
    def make_context_panel(self) -> Panel:
        """Build context building panel."""
        lines = [ctx["msg"] for ctx in list(self.contexts)[-8:]]
        content = "\n".join(lines) if lines else "(no context builds yet)"
        return Panel(content, title="🧠 Context Building", box=box.ROUNDED)
    
    def make_history_panel(self) -> Panel:
        """Build history state panel."""
        content = "\n".join(self.history_state) if self.history_state else "(no history state)"
        return Panel(content, title="📜 History State", box=box.ROUNDED)
    
    def make_error_panel(self) -> Panel:
        """Build errors panel."""
        lines = [f"[{e['time']}] {e['msg']}" for e in list(self.errors)[-8:]]
        content = "\n".join(lines) if lines else "✅ No errors"
        style = "red" if self.errors else "green"
        return Panel(content, title="⚠️ Errors & Warnings", box=box.ROUNDED, style=style)
    
    def make_status_bar(self) -> Panel:
        """Build status bar."""
        status = f"Last Update: {self.last_update or 'N/A'} | Log: {self.log_file} | Requests: {len(self.requests)} | Errors: {len(self.errors)}"
        return Panel(status, box=box.ROUNDED)
    
    def render(self) -> Layout:
        """Render full dashboard."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )
        
        layout["header"].update(
            Panel("🌙 LUNA ENGINE MONITOR — Press Ctrl+C to exit", style="bold blue")
        )
        
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        
        layout["left"].split_column(
            Layout(self.make_request_table()),
            Layout(self.make_route_table()),
        )
        
        layout["right"].split_column(
            Layout(self.make_context_panel()),
            Layout(self.make_history_panel()),
            Layout(self.make_error_panel()),
        )
        
        layout["footer"].update(self.make_status_bar())
        
        return layout
    
    async def run(self):
        """Run the monitor."""
        self.console.print("[bold blue]Starting Luna Monitor...[/]")
        self.console.print(f"Watching: {self.log_file}")
        self.console.print("Press Ctrl+C to exit\n")
        
        # Start at end of file
        if self.log_file.exists():
            self.file_pos = self.log_file.stat().st_size
        
        try:
            with Live(self.render(), refresh_per_second=2, console=self.console) as live:
                while True:
                    self.tail_log()
                    live.update(self.render())
                    await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Monitor stopped[/]")


def main():
    log_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/luna_backend.log"
    monitor = LunaMonitor(log_file)
    asyncio.run(monitor.run())


if __name__ == "__main__":
    main()
