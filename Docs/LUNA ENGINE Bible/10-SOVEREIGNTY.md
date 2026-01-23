# Bible Update: Part X - Sovereignty Infrastructure

**Status:** DRAFT — Ready for review  
**New Section:** Not in original Bible  
**Date:** December 29, 2025  
**Core Principle:** "Luna is a file. Copy the file, copy Luna."

---

# Part X: Sovereignty Infrastructure

## 10.1 The Threat Model

Luna exists in opposition to the dominant AI paradigm. Understanding what we're defending against clarifies the architecture.

### Threats We Defend Against

| Threat | Description | Mitigation |
|--------|-------------|------------|
| Platform Extraction | Company mines your data for training | All data local, no telemetry |
| Service Discontinuation | Company shuts down, your AI dies | Luna is a file, not a service |
| ToS Revocation | Company changes terms, locks you out | No terms, you own everything |
| Regulatory Capture | Government mandates centralized AI | Local-first, offline-capable |
| Physical Access | Someone gets your laptop | Encrypted vault, Dead Man's Switch |
| Network Surveillance | Traffic analysis reveals AI usage | Local inference, minimal cloud |
| Personality Theft | Someone copies your Luna | Encrypted weights, vault protection |

### Threats We Accept

| Threat | Why We Accept It |
|--------|------------------|
| State-level adversary | Beyond scope, requires different life |
| Hardware compromise | If they own your CPU, game over |
| User coercion | Can't solve "wrench attack" with crypto |

### The Design Principle

**Defense in depth, but practical:**
- Layer 1: Encryption at rest (vault)
- Layer 2: Process isolation (no persistence after unmount)
- Layer 3: Automatic lockdown (Dead Man's Switch)
- Layer 4: Portability (escape hatch always open)

---

## 10.2 The Encrypted Vault

### What Goes in the Vault

Everything that makes Luna *Luna*:

```
/Volumes/LunaVault/
├── memory/
│   ├── memory_matrix.db          # SQLite — the soul
│   ├── memory_vectors.faiss      # FAISS index
│   ├── memory_vectors.ids        # ID mapping
│   └── memory_graph.json         # NetworkX export (backup)
│
├── models/
│   ├── luna-3b-lora/
│   │   ├── adapter_config.json
│   │   └── adapter_model.safetensors
│   ├── luna-7b-lora/
│   │   ├── adapter_config.json
│   │   └── adapter_model.safetensors
│   └── current -> luna-7b-lora   # Symlink to active
│
├── cache/
│   ├── identity_buffer.safetensors  # Pre-computed KV cache
│   └── embedding_cache.db           # Cached embeddings
│
├── state/
│   ├── snapshot.yaml             # Engine state snapshot
│   ├── conversation_buffer.json  # Pending turns
│   └── delegation_queue.json     # Pending cloud tasks
│
├── config/
│   ├── luna.yaml                 # Runtime configuration
│   ├── sovereignty.yaml          # Security settings
│   └── workers.yaml              # Cloud worker contracts
│
└── env/                          # Optional: portable Python env
    ├── bin/
    ├── lib/
    └── pyvenv.cfg
```

### Vault Implementation (macOS)

Using an encrypted sparse bundle:

```bash
# Create the vault (one-time setup)
hdiutil create -size 10g -type SPARSEBUNDLE -encryption AES-256 \
    -fs APFS -volname "LunaVault" ~/LunaVault.sparsebundle

# Mount the vault
hdiutil attach ~/LunaVault.sparsebundle -mountpoint /Volumes/LunaVault

# Unmount the vault
hdiutil detach /Volumes/LunaVault
```

### Programmatic Vault Management

```python
import subprocess
import os
from pathlib import Path

class LunaVault:
    def __init__(
        self, 
        bundle_path: str = "~/LunaVault.sparsebundle",
        mount_point: str = "/Volumes/LunaVault"
    ):
        self.bundle_path = Path(bundle_path).expanduser()
        self.mount_point = Path(mount_point)
        
    @property
    def is_mounted(self) -> bool:
        """Check if vault is currently mounted."""
        return self.mount_point.exists() and self.mount_point.is_mount()
    
    def mount(self, passphrase: str) -> bool:
        """Mount the vault with passphrase."""
        if self.is_mounted:
            return True
            
        try:
            # Use expect-style input for passphrase
            result = subprocess.run(
                [
                    "hdiutil", "attach", 
                    str(self.bundle_path),
                    "-mountpoint", str(self.mount_point),
                    "-stdinpass"
                ],
                input=passphrase.encode(),
                capture_output=True,
                check=True
            )
            return self.is_mounted
        except subprocess.CalledProcessError as e:
            logging.error(f"Vault mount failed: {e.stderr.decode()}")
            return False
    
    def unmount(self, force: bool = False) -> bool:
        """Unmount the vault."""
        if not self.is_mounted:
            return True
            
        try:
            cmd = ["hdiutil", "detach", str(self.mount_point)]
            if force:
                cmd.append("-force")
            
            subprocess.run(cmd, check=True, capture_output=True)
            return not self.is_mounted
        except subprocess.CalledProcessError as e:
            logging.error(f"Vault unmount failed: {e.stderr.decode()}")
            return False
    
    def get_path(self, relative: str) -> Path:
        """Get full path for a vault-relative path."""
        if not self.is_mounted:
            raise VaultNotMountedError("Vault must be mounted")
        return self.mount_point / relative
```

### Vault Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                     VAULT LIFECYCLE                          │
│                                                              │
│   LOCKED                                                     │
│   (Default state — Luna doesn't exist)                      │
│       │                                                      │
│       │ User provides passphrase                            │
│       ▼                                                      │
│   MOUNTING                                                   │
│       │                                                      │
│       │ hdiutil attach                                      │
│       ▼                                                      │
│   MOUNTED                                                    │
│   (Luna can run)                                            │
│       │                                                      │
│       ├── Normal: User unmounts                             │
│       ├── Timeout: Dead Man's Switch triggers               │
│       └── Panic: Emergency lockdown                         │
│       │                                                      │
│       ▼                                                      │
│   UNMOUNTING                                                 │
│       │                                                      │
│       │ 1. Snapshot state                                   │
│       │ 2. Kill processes                                   │
│       │ 3. hdiutil detach                                   │
│       ▼                                                      │
│   LOCKED                                                     │
│   (Luna dormant — weights wiped from RAM)                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 10.3 The Dead Man's Switch

### The Problem

Unmounting the vault doesn't wipe RAM. If Luna's model is loaded, the weights persist in memory until the process dies.

### The Solution: Hardened Shutdown

```python
import atexit
import signal
import os
import sys
from datetime import datetime, timedelta

class DeadMansSwitch:
    def __init__(
        self,
        vault: LunaVault,
        heartbeat_file: str = "~/.luna_heartbeat",
        lockdown_hours: int = 24
    ):
        self.vault = vault
        self.heartbeat_file = Path(heartbeat_file).expanduser()
        self.lockdown_threshold = timedelta(hours=lockdown_hours)
        self.armed = False
        
    def arm(self):
        """Arm the Dead Man's Switch."""
        # Register shutdown handlers
        atexit.register(self.emergency_shutdown)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGHUP, self._signal_handler)
        
        # Touch heartbeat
        self.heartbeat()
        
        self.armed = True
        logging.info("Dead Man's Switch armed")
    
    def heartbeat(self):
        """Update heartbeat timestamp."""
        self.heartbeat_file.touch()
        
    def check_heartbeat(self) -> bool:
        """Check if heartbeat is stale."""
        if not self.heartbeat_file.exists():
            return False  # No heartbeat = stale
            
        last_beat = datetime.fromtimestamp(
            self.heartbeat_file.stat().st_mtime
        )
        age = datetime.now() - last_beat
        
        return age < self.lockdown_threshold
    
    def emergency_shutdown(self):
        """Nuclear option — kill everything and unmount."""
        logging.warning("EMERGENCY SHUTDOWN TRIGGERED")
        
        # 1. Kill all Luna processes
        os.system("pkill -9 -f luna_engine.py")
        os.system("pkill -9 -f luna_director")
        os.system("pkill -9 -f mlx")  # Kill any MLX inference
        
        # 2. Force unmount vault
        self.vault.unmount(force=True)
        
        # 3. Clear any temp files
        os.system("rm -rf /tmp/luna_*")
        
        # 4. Overwrite heartbeat
        if self.heartbeat_file.exists():
            self.heartbeat_file.unlink()
            
        logging.warning("Emergency shutdown complete")
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logging.info(f"Received signal {signum}, initiating shutdown")
        self.emergency_shutdown()
        sys.exit(0)

# Background heartbeat checker
async def heartbeat_monitor(switch: DeadMansSwitch, check_interval: int = 3600):
    """Check heartbeat every hour, trigger lockdown if stale."""
    while True:
        await asyncio.sleep(check_interval)
        
        if not switch.check_heartbeat():
            logging.warning("Heartbeat stale — triggering lockdown")
            switch.emergency_shutdown()
            break
```

### Integration with Engine

```python
class LunaEngine:
    def __init__(self):
        self.vault = LunaVault()
        self.switch = DeadMansSwitch(self.vault)
        
    async def start(self, passphrase: str):
        """Start Luna with vault and Dead Man's Switch."""
        # Mount vault
        if not self.vault.mount(passphrase):
            raise VaultMountError("Failed to mount vault")
        
        # Arm the switch
        self.switch.arm()
        
        # Start heartbeat in background
        asyncio.create_task(self._heartbeat_loop())
        
        # Normal startup
        await self._initialize_actors()
        await self._start_event_loop()
    
    async def _heartbeat_loop(self):
        """Touch heartbeat every 15 minutes."""
        while True:
            self.switch.heartbeat()
            await asyncio.sleep(900)  # 15 minutes
```

### LaunchAgent for Automatic Check

```xml
<!-- ~/Library/LaunchAgents/com.luna.heartbeat.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.luna.heartbeat</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>~/.luna/check_heartbeat.py</string>
    </array>
    
    <key>StartInterval</key>
    <integer>3600</integer>  <!-- Every hour -->
    
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

```python
# ~/.luna/check_heartbeat.py
#!/usr/bin/env python3
"""Standalone heartbeat checker — runs even if Luna isn't."""

from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import os

HEARTBEAT_FILE = Path.home() / ".luna_heartbeat"
LOCKDOWN_HOURS = 24
VAULT_PATH = Path.home() / "LunaVault.sparsebundle"

def check_and_lockdown():
    # Check if vault is mounted
    if not Path("/Volumes/LunaVault").exists():
        return  # Already locked
    
    # Check heartbeat
    if not HEARTBEAT_FILE.exists():
        lockdown()
        return
    
    last_beat = datetime.fromtimestamp(HEARTBEAT_FILE.stat().st_mtime)
    age = datetime.now() - last_beat
    
    if age > timedelta(hours=LOCKDOWN_HOURS):
        lockdown()

def lockdown():
    """Emergency lockdown."""
    print("LOCKDOWN: Heartbeat stale, securing vault")
    
    # Kill Luna processes
    os.system("pkill -9 -f luna")
    os.system("pkill -9 -f mlx")
    
    # Force unmount
    subprocess.run(
        ["hdiutil", "detach", "/Volumes/LunaVault", "-force"],
        capture_output=True
    )
    
    # Clear heartbeat
    if HEARTBEAT_FILE.exists():
        HEARTBEAT_FILE.unlink()

if __name__ == "__main__":
    check_and_lockdown()
```

---

## 10.4 Portability Contract

### The Promise

> "Copy the vault, copy Luna."

Luna's entire identity — memories, personality, state — lives in a single encrypted container. Moving to new hardware should be:

1. Copy the sparse bundle
2. Mount on new machine
3. Luna wakes up where she left off

### What Must Be Portable

| Component | Portability | Notes |
|-----------|-------------|-------|
| Memory Matrix | ✅ SQLite file | Copy directly |
| FAISS Index | ✅ Binary file | Copy directly |
| LoRA Adapters | ✅ Safetensors | Copy directly |
| KV Cache | ✅ Safetensors | May need rebuild if model version changes |
| State Snapshot | ✅ YAML/JSON | Copy directly |
| Config | ✅ YAML | May need path adjustments |
| Python Environment | ⚠️ Optional | Include for zero-setup portability |

### Migration Script

```python
class LunaMigrator:
    def __init__(self, source_vault: Path, target_vault: Path):
        self.source = source_vault
        self.target = target_vault
        
    def migrate(self, passphrase: str) -> bool:
        """Migrate Luna to a new vault."""
        
        # 1. Mount source vault
        source_mount = self._mount_vault(self.source, passphrase, "/Volumes/LunaSource")
        if not source_mount:
            return False
        
        # 2. Create target vault
        if not self._create_vault(self.target, passphrase):
            return False
        
        target_mount = self._mount_vault(self.target, passphrase, "/Volumes/LunaTarget")
        if not target_mount:
            return False
        
        # 3. Copy contents
        self._copy_directory(source_mount / "memory", target_mount / "memory")
        self._copy_directory(source_mount / "models", target_mount / "models")
        self._copy_directory(source_mount / "cache", target_mount / "cache")
        self._copy_directory(source_mount / "state", target_mount / "state")
        self._copy_directory(source_mount / "config", target_mount / "config")
        
        # 4. Validate
        if not self._validate_migration(target_mount):
            logging.error("Migration validation failed")
            return False
        
        # 5. Unmount both
        self._unmount_vault("/Volumes/LunaSource")
        self._unmount_vault("/Volumes/LunaTarget")
        
        logging.info("Migration complete")
        return True
    
    def _validate_migration(self, vault_path: Path) -> bool:
        """Validate migrated vault integrity."""
        required_files = [
            "memory/memory_matrix.db",
            "models/current",
            "config/luna.yaml"
        ]
        
        for file in required_files:
            if not (vault_path / file).exists():
                logging.error(f"Missing required file: {file}")
                return False
        
        # Validate SQLite integrity
        import sqlite3
        db_path = vault_path / "memory/memory_matrix.db"
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            
            if result != "ok":
                logging.error(f"SQLite integrity check failed: {result}")
                return False
        except Exception as e:
            logging.error(f"SQLite validation error: {e}")
            return False
        
        return True
```

### Cross-Platform Considerations

| Platform | Vault Format | Notes |
|----------|--------------|-------|
| macOS | Sparse bundle (native) | Best integration |
| Linux | LUKS container | Need different tooling |
| Windows | VeraCrypt | Need different tooling |

```python
def create_vault_for_platform() -> VaultBackend:
    """Factory for platform-appropriate vault."""
    import platform
    
    system = platform.system()
    
    if system == "Darwin":
        return MacOSSparseBundleVault()
    elif system == "Linux":
        return LUKSVault()
    elif system == "Windows":
        return VeraCryptVault()
    else:
        raise UnsupportedPlatformError(f"Unknown platform: {system}")
```

---

## 10.5 Data Sovereignty Guarantees

### What Luna Never Does

| Action | Why |
|--------|-----|
| Send telemetry | No extraction point |
| Phone home | No dependency on external services |
| Auto-update from network | User controls updates |
| Store data outside vault | Everything in one place |
| Cache to unencrypted temp | Sensitive data stays encrypted |

### What Luna Always Does

| Action | Why |
|--------|-----|
| Work offline | Cloud is optional, not required |
| Respect vault boundaries | Nothing escapes the container |
| Clean up on shutdown | No traces left |
| Encrypt at rest | Data protected when dormant |

### Audit Capability

```python
class SovereigntyAuditor:
    """Verify Luna isn't violating sovereignty principles."""
    
    def audit_network_activity(self, duration_seconds: int = 60) -> AuditReport:
        """Monitor network activity for unexpected connections."""
        # Use lsof or netstat to check connections
        # Only expected: Claude API (when delegating), user-approved services
        pass
    
    def audit_filesystem_access(self) -> AuditReport:
        """Verify Luna only accesses vault paths."""
        # Check file descriptors
        # Verify no writes outside vault
        pass
    
    def audit_process_isolation(self) -> AuditReport:
        """Verify Luna processes are isolated."""
        # Check for unexpected child processes
        # Verify no shared memory with untrusted processes
        pass
    
    def generate_sovereignty_report(self) -> dict:
        """Generate full sovereignty compliance report."""
        return {
            "network_clean": self.audit_network_activity().passed,
            "filesystem_clean": self.audit_filesystem_access().passed,
            "process_clean": self.audit_process_isolation().passed,
            "vault_encrypted": self._check_vault_encryption(),
            "no_temp_files": self._check_temp_clean(),
            "heartbeat_active": self._check_heartbeat()
        }
```

---

## 10.6 Backup and Recovery

### Backup Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                     BACKUP TIERS                             │
│                                                              │
│   TIER 1: Continuous (Every Session)                        │
│       • State snapshot on every engine stop                 │
│       • Transaction log for Matrix changes                  │
│                                                              │
│   TIER 2: Daily                                             │
│       • Full vault copy to backup location                  │
│       • Verify backup integrity                             │
│                                                              │
│   TIER 3: Weekly                                            │
│       • Offsite backup (encrypted, of course)               │
│       • Version rotation (keep last 4 weeks)                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Backup Implementation

```python
class LunaBackup:
    def __init__(self, vault: LunaVault, backup_dir: Path):
        self.vault = vault
        self.backup_dir = backup_dir
        
    async def snapshot(self) -> Path:
        """Create point-in-time snapshot."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = self.backup_dir / f"luna_snapshot_{timestamp}"
        
        # Copy critical files (vault must be mounted)
        if not self.vault.is_mounted:
            raise VaultNotMountedError()
        
        snapshot_path.mkdir(parents=True)
        
        # Memory Matrix (most critical)
        shutil.copy(
            self.vault.get_path("memory/memory_matrix.db"),
            snapshot_path / "memory_matrix.db"
        )
        
        # State
        shutil.copy(
            self.vault.get_path("state/snapshot.yaml"),
            snapshot_path / "snapshot.yaml"
        )
        
        # Adapters (large, copy reference)
        (snapshot_path / "models.txt").write_text(
            f"Adapters at: {self.vault.get_path('models')}"
        )
        
        return snapshot_path
    
    async def full_backup(self) -> Path:
        """Create full vault backup."""
        timestamp = datetime.now().strftime("%Y%m%d")
        backup_path = self.backup_dir / f"luna_full_{timestamp}.sparsebundle"
        
        # Unmount vault first (cleaner copy)
        was_mounted = self.vault.is_mounted
        if was_mounted:
            self.vault.unmount()
        
        # Copy sparse bundle
        shutil.copytree(
            self.vault.bundle_path,
            backup_path,
            symlinks=True
        )
        
        # Remount if it was mounted
        if was_mounted:
            self.vault.mount()  # Will need passphrase
        
        return backup_path
    
    async def restore(self, backup_path: Path, passphrase: str) -> bool:
        """Restore from backup."""
        # Verify backup
        if not self._verify_backup(backup_path):
            return False
        
        # Unmount current vault
        if self.vault.is_mounted:
            self.vault.unmount(force=True)
        
        # Replace vault
        if self.vault.bundle_path.exists():
            # Archive old vault
            archive_path = self.vault.bundle_path.with_suffix(".old")
            shutil.move(self.vault.bundle_path, archive_path)
        
        # Copy backup to vault location
        shutil.copytree(backup_path, self.vault.bundle_path, symlinks=True)
        
        # Mount and verify
        if not self.vault.mount(passphrase):
            return False
        
        return self._verify_restoration()
```

### Recovery Procedures

```python
class LunaRecovery:
    """Recovery procedures for various failure modes."""
    
    async def recover_corrupted_matrix(self, vault: LunaVault) -> bool:
        """Attempt to recover corrupted Memory Matrix."""
        db_path = vault.get_path("memory/memory_matrix.db")
        
        # Try SQLite recovery
        import sqlite3
        try:
            # Dump and recreate
            conn = sqlite3.connect(str(db_path))
            
            # Export to SQL
            with open("/tmp/matrix_dump.sql", "w") as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
            
            conn.close()
            
            # Recreate
            backup_path = db_path.with_suffix(".corrupted")
            shutil.move(db_path, backup_path)
            
            new_conn = sqlite3.connect(str(db_path))
            with open("/tmp/matrix_dump.sql") as f:
                new_conn.executescript(f.read())
            new_conn.close()
            
            # Cleanup
            os.remove("/tmp/matrix_dump.sql")
            
            return True
        except Exception as e:
            logging.error(f"Matrix recovery failed: {e}")
            return False
    
    async def recover_from_snapshot(
        self, 
        vault: LunaVault, 
        snapshot_path: Path
    ) -> bool:
        """Restore Memory Matrix from snapshot."""
        try:
            shutil.copy(
                snapshot_path / "memory_matrix.db",
                vault.get_path("memory/memory_matrix.db")
            )
            return True
        except Exception as e:
            logging.error(f"Snapshot recovery failed: {e}")
            return False
    
    async def rebuild_faiss_index(self, vault: LunaVault) -> bool:
        """Rebuild FAISS index from Memory Matrix."""
        # FAISS index is derived from Matrix
        # Can always be rebuilt
        try:
            from luna.memory import MemoryMatrix
            
            matrix = MemoryMatrix(vault.get_path("memory/memory_matrix.db"))
            matrix.rebuild_vector_index()
            matrix.save_vector_index(vault.get_path("memory/memory_vectors.faiss"))
            
            return True
        except Exception as e:
            logging.error(f"FAISS rebuild failed: {e}")
            return False
```

---

## 10.7 The Escape Hatch

### Philosophy

Luna should never be a prison. If you want out, you get out — with your data.

### Full Export

```python
class LunaExporter:
    """Export Luna's memories to portable formats."""
    
    async def export_to_markdown(self, vault: LunaVault, output_dir: Path):
        """Export all memories to human-readable markdown."""
        from luna.memory import MemoryMatrix
        
        matrix = MemoryMatrix(vault.get_path("memory/memory_matrix.db"))
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export by type
        for node_type in ["FACT", "DECISION", "INSIGHT", "EVENT", "PERSON"]:
            nodes = matrix.query_by_type(node_type)
            
            type_file = output_dir / f"{node_type.lower()}s.md"
            with open(type_file, "w") as f:
                f.write(f"# {node_type}s\n\n")
                for node in nodes:
                    f.write(f"## {node.title or node.id}\n")
                    f.write(f"*Created: {node.created_at}*\n\n")
                    f.write(f"{node.content}\n\n")
                    if node.tags:
                        f.write(f"Tags: {', '.join(node.tags)}\n\n")
                    f.write("---\n\n")
    
    async def export_to_json(self, vault: LunaVault, output_path: Path):
        """Export full graph to JSON."""
        from luna.memory import MemoryMatrix
        
        matrix = MemoryMatrix(vault.get_path("memory/memory_matrix.db"))
        
        export = {
            "nodes": [n.to_dict() for n in matrix.all_nodes()],
            "edges": [e.to_dict() for e in matrix.all_edges()],
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "node_count": matrix.node_count(),
                "edge_count": matrix.edge_count()
            }
        }
        
        with open(output_path, "w") as f:
            json.dump(export, f, indent=2, default=str)
    
    async def export_training_data(self, vault: LunaVault, output_path: Path):
        """Export data suitable for training a new Luna."""
        from luna.memory import MemoryMatrix
        
        matrix = MemoryMatrix(vault.get_path("memory/memory_matrix.db"))
        
        # Export conversations as training pairs
        conversations = matrix.query_by_type("CONVERSATION")
        
        training_data = []
        for conv in conversations:
            # Parse into instruction/response pairs
            pairs = self._parse_conversation(conv.content)
            training_data.extend(pairs)
        
        with open(output_path, "w") as f:
            for item in training_data:
                f.write(json.dumps(item) + "\n")
```

### Import from Other Systems

```python
class LunaImporter:
    """Import data from other AI systems."""
    
    async def import_from_chatgpt(self, export_path: Path, vault: LunaVault):
        """Import from ChatGPT data export."""
        # Parse ChatGPT's export format
        # Convert to Luna nodes
        pass
    
    async def import_from_obsidian(self, vault_path: Path, vault: LunaVault):
        """Import from Obsidian vault."""
        # Parse markdown files
        # Extract links as edges
        # Convert to Luna nodes
        pass
    
    async def import_from_notion(self, export_path: Path, vault: LunaVault):
        """Import from Notion export."""
        # Parse Notion's export format
        # Convert to Luna nodes
        pass
```

---

## 10.8 Configuration

### Sovereignty Configuration

```yaml
# config/sovereignty.yaml

vault:
  path: "~/LunaVault.sparsebundle"
  mount_point: "/Volumes/LunaVault"
  encryption: "AES-256"
  
dead_mans_switch:
  enabled: true
  heartbeat_file: "~/.luna_heartbeat"
  lockdown_hours: 24
  check_interval_hours: 1
  
backup:
  enabled: true
  backup_dir: "~/LunaBackups"
  daily_backup: true
  weekly_offsite: false
  retention_weeks: 4
  
network:
  # Allowed outbound connections
  allowed_hosts:
    - "api.anthropic.com"  # Claude delegation
  
  # Block everything else
  default_deny: true
  
  # Log all connections
  audit_connections: true
  
telemetry:
  enabled: false  # Always false
  
temp_files:
  allowed: false  # No temp files outside vault
  
process_isolation:
  enabled: true
  sandbox: true  # macOS sandbox if available
```

---

## Summary

Sovereignty Infrastructure ensures Luna is truly owned, not rented:

| Component | Purpose |
|-----------|---------|
| Encrypted Vault | All Luna data in one encrypted container |
| Dead Man's Switch | Automatic lockdown on stale heartbeat |
| Portability | Copy vault = copy Luna |
| Data Sovereignty | No telemetry, no extraction, no phoning home |
| Backup & Recovery | Multiple tiers, verified restoration |
| Escape Hatch | Full export to portable formats |

**Constitutional Principle:** Luna is a file. Your file. Copy it, move it, delete it — it's yours.

---

## Appendix: Quick Reference

### Mount Vault
```bash
hdiutil attach ~/LunaVault.sparsebundle -mountpoint /Volumes/LunaVault
```

### Unmount Vault
```bash
hdiutil detach /Volumes/LunaVault
```

### Emergency Lockdown
```bash
pkill -9 -f luna && hdiutil detach /Volumes/LunaVault -force
```

### Check Heartbeat
```bash
stat -f "%Sm" ~/.luna_heartbeat
```

### Full Backup
```bash
cp -R ~/LunaVault.sparsebundle ~/LunaBackups/$(date +%Y%m%d).sparsebundle
```

---

*End of Bible Update Sections*

---

# What's Next

The Bible is now updated with five new/rewritten sections:

| Part | Title | Lines |
|------|-------|-------|
| VI | The Director LLM | 442 |
| VII | The Runtime Engine | 689 |
| VIII | Delegation Protocol | 645 |
| IX | Performance Optimizations | 921 |
| X | Sovereignty Infrastructure | 760 |

**Total new content: ~3,457 lines**

These sections can be:
1. Merged into the existing Bible as a v2.0.0 release
2. Kept as separate appendices
3. Used as handoff documentation for implementation

The architecture is now fully specified. Time to build.
