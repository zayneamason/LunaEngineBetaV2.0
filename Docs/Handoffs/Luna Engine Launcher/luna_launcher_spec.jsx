import { useState } from "react";

const C = {
  bg: "#0a0e17",
  surface: "#111827",
  surfaceHover: "#1a2332",
  border: "#1e293b",
  borderActive: "#7c3aed",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textDim: "#64748b",
  accent: "#7c3aed",
  accentSoft: "#7c3aed22",
  warm: "#f59e0b",
  warmSoft: "#f59e0b22",
  green: "#10b981",
  greenSoft: "#10b98122",
  red: "#ef4444",
  redSoft: "#ef444422",
  blue: "#3b82f6",
  blueSoft: "#3b82f622",
  cyan: "#06b6d4",
  cyanSoft: "#06b6d422",
};

const fontMono = "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace";
const fontBody = "'Inter', -apple-system, sans-serif";

const TABS = ["Launcher UI", "Architecture", "Config Format", "CLI Spec", "Wiring", "Files & Tests"];

function CodeBlock({ title, code }) {
  return (
    <div>
      {title && (
        <div style={{ fontSize: 12, color: C.textDim, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>
          {title}
        </div>
      )}
      <div style={{
        background: "#0d1117",
        borderRadius: 8,
        padding: 20,
        fontFamily: fontMono,
        fontSize: 11.5,
        color: C.text,
        lineHeight: 1.7,
        whiteSpace: "pre-wrap",
        border: "1px solid " + C.border,
        overflow: "auto",
      }}>
        {code}
      </div>
    </div>
  );
}

function InfoBox({ color, label, children }) {
  return (
    <div style={{
      background: color + "15",
      borderRadius: 10,
      padding: 20,
      border: "1px solid " + color + "33",
    }}>
      <div style={{ fontSize: 12, color: color, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 10 }}>
        {label}
      </div>
      {children}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 0: Launcher UI Prototype
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function LauncherUITab() {
  const [config, setConfig] = useState({
    backend: { port: 8000, enabled: true },
    frontend: { port: 5173, enabled: true },
    observatory: { port: 8100, enabled: false },
    tunnel: { enabled: false },
  });

  const [statuses, setStatuses] = useState({
    backend: "stopped",
    frontend: "stopped",
    observatory: "stopped",
    tunnel: "stopped",
  });

  const [tunnelUrl, setTunnelUrl] = useState(null);

  const toggleService = (key) => {
    setConfig(prev => ({
      ...prev,
      [key]: { ...prev[key], enabled: !prev[key].enabled },
    }));
  };

  const setPort = (key, port) => {
    const num = parseInt(port) || 0;
    setConfig(prev => ({
      ...prev,
      [key]: { ...prev[key], port: num },
    }));
  };

  const simulateLaunch = () => {
    Object.keys(config).forEach((key, i) => {
      if (config[key].enabled) {
        setTimeout(() => {
          setStatuses(prev => ({ ...prev, [key]: "starting" }));
        }, i * 400);
        setTimeout(() => {
          setStatuses(prev => ({ ...prev, [key]: "running" }));
          if (key === "tunnel") setTunnelUrl("https://luna-abc123.trycloudflare.com");
        }, i * 400 + 1200);
      }
    });
  };

  const simulateStop = () => {
    setStatuses({ backend: "stopped", frontend: "stopped", observatory: "stopped", tunnel: "stopped" });
    setTunnelUrl(null);
  };

  const anyRunning = Object.values(statuses).some(s => s === "running" || s === "starting");

  const services = [
    { key: "backend", label: "Luna Backend", desc: "FastAPI server -- message processing, memory, delegation", icon: "gear", defaultPort: 8000 },
    { key: "frontend", label: "Eclissi Frontend", desc: "Vite dev server -- chat UI, observatory, Kozmo", icon: "screen", defaultPort: 5173 },
    { key: "observatory", label: "Observatory Sandbox", desc: "Memory Matrix debug server -- graph visualization", icon: "scope", defaultPort: 8100 },
    { key: "tunnel", label: "Cloudflare Tunnel", desc: "Public URL -- for Google Sheets sidebar + remote access", icon: "globe", hasPort: false },
  ];

  var statusColor = function(s) {
    if (s === "running") return C.green;
    if (s === "starting") return C.warm;
    return C.textDim;
  };

  var statusLabel = function(s) {
    if (s === "running") return "Running";
    if (s === "starting") return "Starting...";
    return "Stopped";
  };

  var generatedCommand = function() {
    var parts = ["./scripts/launch_luna.sh"];
    if (config.backend.enabled && config.backend.port !== 8000) parts.push("--backend-port " + config.backend.port);
    if (config.frontend.enabled && config.frontend.port !== 5173) parts.push("--frontend-port " + config.frontend.port);
    if (config.observatory.enabled) {
      parts.push("--observatory");
      if (config.observatory.port !== 8100) parts.push("--observatory-port " + config.observatory.port);
    }
    if (config.tunnel.enabled) parts.push("--tunnel");
    if (!config.backend.enabled) parts.push("--no-backend");
    if (!config.frontend.enabled) parts.push("--no-frontend");
    return parts.join(" ");
  };

  var generatedConfig = function() {
    return JSON.stringify({
      services: {
        backend: { port: config.backend.port, enabled: config.backend.enabled },
        frontend: { port: config.frontend.port, enabled: config.frontend.enabled },
        observatory: { port: config.observatory.port, enabled: config.observatory.enabled },
        tunnel: { enabled: config.tunnel.enabled },
      },
    }, null, 2);
  };

  var iconMap = { gear: "\u2699\uFE0F", screen: "\uD83D\uDDA5", scope: "\uD83D\uDD2D", globe: "\uD83C\uDF10" };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>
        This is what the launcher UI feels like. Configure ports, toggle services, hit launch.
        Below the UI you will see the generated CLI command and config file.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {services.map(function(svc) {
          var cfg = config[svc.key];
          var status = statuses[svc.key];
          return (
            <div key={svc.key} style={{
              background: cfg.enabled ? C.surface : C.surface + "88",
              borderRadius: 10,
              padding: 18,
              border: "1px solid " + (cfg.enabled ? C.border : C.border + "66"),
              opacity: cfg.enabled ? 1 : 0.6,
              transition: "all 0.2s",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 18 }}>{iconMap[svc.icon] || ""}</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: C.text }}>{svc.label}</span>
                </div>
                <button onClick={function() { toggleService(svc.key); }} style={{
                  background: cfg.enabled ? C.accent : C.surfaceHover,
                  color: cfg.enabled ? "#fff" : C.textDim,
                  border: "1px solid " + (cfg.enabled ? C.accent : C.border),
                  borderRadius: 12, padding: "4px 12px", fontSize: 11, cursor: "pointer", fontFamily: fontBody,
                }}>
                  {cfg.enabled ? "ON" : "OFF"}
                </button>
              </div>
              <div style={{ fontSize: 12, color: C.textDim, marginBottom: 12 }}>{svc.desc}</div>
              {svc.hasPort !== false && cfg.enabled && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <span style={{ fontSize: 12, color: C.textMuted, fontFamily: fontMono }}>port:</span>
                  <input
                    type="number"
                    value={cfg.port}
                    onChange={function(e) { setPort(svc.key, e.target.value); }}
                    style={{
                      background: C.bg, color: C.text, border: "1px solid " + C.border,
                      borderRadius: 6, padding: "6px 10px", fontSize: 13, fontFamily: fontMono, width: 80, outline: "none",
                    }}
                  />
                  {cfg.port !== svc.defaultPort && (
                    <span style={{ fontSize: 11, color: C.warm }}>{"(default: " + svc.defaultPort + ")"}</span>
                  )}
                </div>
              )}
              <div style={{ fontSize: 12, fontFamily: fontMono, color: statusColor(status) }}>
                {status === "running" ? "\u25CF " : status === "starting" ? "\u25D0 " : "\u25CB "}
                {statusLabel(status)}
                {svc.key === "tunnel" && tunnelUrl && status === "running" && (
                  <span style={{ color: C.cyan, marginLeft: 8 }}>{tunnelUrl}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <button onClick={simulateLaunch} disabled={anyRunning} style={{
          background: anyRunning ? C.surfaceHover : C.green,
          color: anyRunning ? C.textDim : "#fff",
          border: "none", borderRadius: 8, padding: "12px 28px", fontSize: 14, fontWeight: 600,
          cursor: anyRunning ? "not-allowed" : "pointer", fontFamily: fontBody,
        }}>
          {anyRunning ? "Running..." : "Launch Luna"}
        </button>
        {anyRunning && (
          <button onClick={simulateStop} style={{
            background: C.redSoft, color: C.red, border: "1px solid " + C.red + "44",
            borderRadius: 8, padding: "12px 28px", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: fontBody,
          }}>
            Stop All
          </button>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <CodeBlock title="Generated CLI Command" code={generatedCommand()} />
        <CodeBlock title="Generated luna.launch.json" code={generatedConfig()} />
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 1: Architecture
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function ArchitectureTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{
        background: "linear-gradient(135deg, " + C.accentSoft + ", " + C.cyanSoft + ")",
        borderRadius: 12, padding: "24px 28px", border: "1px solid " + C.border,
      }}>
        <div style={{ fontSize: 13, color: C.accent, fontWeight: 600, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 10 }}>
          Design Principle
        </div>
        <div style={{ fontSize: 18, color: C.text, lineHeight: 1.5 }}>
          One config file &rarr; one CLI script &rarr; all services
        </div>
        <div style={{ fontSize: 13, color: C.textMuted, marginTop: 6 }}>
          config/luna.launch.json is the single source of truth. The CLI reads it. The UI writes it. Nothing is hardcoded.
        </div>
      </div>

      <CodeBlock title="System Architecture" code={
"+---------------------------------------------------------+\n" +
"|                   luna.launch.json                       |\n" +
"|              config/luna.launch.json                     |\n" +
"|  +-----------------------------------------------------+|\n" +
"|  | { services: { backend: { port: 8000 }, ... } }      ||\n" +
"|  +-----------------------------------------------------+|\n" +
"+----------------+------------------------+---------------+\n" +
"                 |                        |\n" +
"        +--------v-------+       +--------v--------+\n" +
"        |  CLI Script    |       |   Config UI     |\n" +
"        |  launch_luna   |       |   (HTML file)   |\n" +
"        |  .sh           |<------+   reads/writes  |\n" +
"        |                |       |   the JSON      |\n" +
"        +--------+-------+       +-----------------+\n" +
"                 |\n" +
"    +------------+----------+--------------+\n" +
"    |            |          |              |\n" +
"    v            v          v              v\n" +
"+--------+ +--------+ +----------+ +---------+\n" +
"|Backend | |Frontend| |Observa-  | |Tunnel   |\n" +
"|:8000   | |:5173   | |tory:8100 | |(cloud-  |\n" +
"|uvicorn | |vite    | |sandbox   | |flared)  |\n" +
"+--------+ +--------+ +----------+ +---------+\n" +
"                                       |\n" +
"                                       v\n" +
"                                  +----------+\n" +
"                                  |Apps      |\n" +
"                                  |Script    |\n" +
"                                  |sidebar   |\n" +
"                                  |URL patch |\n" +
"                                  +----------+"
      } />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <InfoBox color={C.green} label="What Changes">
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.8 }}>
            <strong style={{ color: C.text }}>launch_luna.sh</strong> -- rewritten to read config, accept CLI overrides, launch all 4 services<br/>
            <strong style={{ color: C.text }}>vite.config.js</strong> -- reads ports from env vars set by launcher<br/>
            <strong style={{ color: C.text }}>NEW: config/luna.launch.json</strong> -- port and service config<br/>
            <strong style={{ color: C.text }}>NEW: scripts/luna_launcher.html</strong> -- config UI
          </div>
        </InfoBox>
        <InfoBox color={C.blue} label="What Stays the Same">
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.8 }}>
            <strong style={{ color: C.text }}>run.py</strong> -- still uses --port flag, launcher just passes it<br/>
            <strong style={{ color: C.text }}>server.py</strong> -- no changes, port comes from uvicorn<br/>
            <strong style={{ color: C.text }}>Frontend source</strong> -- already uses relative URLs<br/>
            <strong style={{ color: C.text }}>Observatory MCP</strong> -- already has port config
          </div>
        </InfoBox>
      </div>

      <InfoBox color={C.cyan} label="Key Mechanism: Vite Proxy Ports">
        <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>
          Currently vite.config.js has 8 proxy routes hardcoded to localhost:8000.
          The fix: read from env vars that the launcher sets before calling npm run dev.
          Vite exposes process.env in config files. Zero runtime impact.
          Falls back to current defaults if env vars are absent -- so plain npm run dev still works.
        </div>
      </InfoBox>

      <CodeBlock title="Launch Sequence" code={
"1. READ config/luna.launch.json (merge with CLI overrides)\n\n" +
"2. PRE-FLIGHT CHECKS\n" +
"   +-- For each enabled service:\n" +
"   |   +-- Is port available? (lsof -i :PORT)\n" +
"   |   |   +-- YES -> continue\n" +
"   |   |   +-- NO  -> show PID + process name, ask to kill or skip\n" +
"   |   +-- Are dependencies met? (python? node? cloudflared?)\n" +
"   +-- Report: 'Ready to launch: backend:8000, frontend:5173'\n\n" +
"3. LAUNCH SERVICES (ordered -- backend first, frontend needs backend)\n" +
"   +-- Backend:     python scripts/run.py --server --port PORT\n" +
"   |                wait for /health to respond (30s timeout)\n" +
"   +-- Frontend:    LUNA_BACKEND_PORT=... npm run dev\n" +
"   |                wait for port to open\n" +
"   +-- Observatory: python mcp_server/server.py --http-only --port PORT\n" +
"   |                wait for port to open\n" +
"   +-- Tunnel:      cloudflared tunnel --url http://localhost:PORT\n" +
"                    capture URL, patch Apps Script sidebar\n\n" +
"4. STATUS DISPLAY\n" +
"   +---------------------------------------------------+\n" +
"   | Luna Engine Launcher                              |\n" +
"   |                                                   |\n" +
"   | * Backend     :8000  (PID 12345)                  |\n" +
"   | * Frontend    :5173  (PID 12346)                  |\n" +
"   | - Observatory :8100  (disabled)                   |\n" +
"   | * Tunnel      https://luna-abc.trycloudflare...   |\n" +
"   |                                                   |\n" +
"   | Press Ctrl+C to stop all.                         |\n" +
"   +---------------------------------------------------+\n\n" +
"5. CLEANUP (Ctrl+C / trap)\n" +
"   +-- Kill all spawned PIDs\n" +
"   +-- Restore Apps Script sidebar URL to localhost\n" +
"   +-- Report: 'All services stopped.'"
      } />
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 2: Config Format
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function ConfigFormatTab() {
  var configJSON = JSON.stringify({
    services: {
      backend: { port: 8000, enabled: true, host: "0.0.0.0", debug: false },
      frontend: { port: 5173, enabled: true },
      observatory: { port: 8100, enabled: false, start_production: false },
      tunnel: { enabled: false, patch_apps_script: true },
    },
    profiles: {
      "default": { services: { backend: { enabled: true }, frontend: { enabled: true }, observatory: { enabled: false }, tunnel: { enabled: false } } },
      full: { services: { backend: { enabled: true }, frontend: { enabled: true }, observatory: { enabled: true }, tunnel: { enabled: true } } },
      "api-only": { services: { backend: { enabled: true }, frontend: { enabled: false }, observatory: { enabled: false }, tunnel: { enabled: false } } },
    },
  }, null, 2);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <CodeBlock title="config/luna.launch.json -- full schema" code={configJSON} />

      <InfoBox color={C.accent} label="Design Decisions">
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            ["Profiles for common setups", "Don't want to toggle 4 switches every time. 'default' = backend+frontend. 'full' = everything. 'api-only' = headless."],
            ["Flat JSON, no nesting hell", "One level of service config. Profiles just override the top-level service settings."],
            ["Lives in config/ with other configs", "Not a dotfile. Not in root. Alongside llm_providers.json and personality.json."],
            ["debug flag on backend only", "Controls logging level. Frontend debug is always available via browser devtools."],
            ["observatory.start_production", "Sandbox starts in sandbox mode by default. This flag starts it pointed at prod Memory Matrix."],
          ].map(function(item, i) {
            return (
              <div key={i} style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.5 }}>
                <strong style={{ color: C.text }}>{item[0]}</strong> -- {item[1]}
              </div>
            );
          })}
        </div>
      </InfoBox>

      <CodeBlock title="CLI override precedence" code={
"# Priority (highest to lowest):\n" +
"#\n" +
"# 1. CLI flags           --backend-port 9000\n" +
"# 2. Environment vars    LUNA_BACKEND_PORT=9000\n" +
"# 3. luna.launch.json    { services: { backend: { port: 9000 } } }\n" +
"# 4. Hardcoded defaults  8000\n" +
"#\n" +
"# Examples:\n" +
"./scripts/launch_luna.sh                          # Read from config\n" +
"./scripts/launch_luna.sh --profile full           # Use 'full' profile\n" +
"./scripts/launch_luna.sh --backend-port 9000      # Override backend port\n" +
"./scripts/launch_luna.sh --no-frontend --tunnel   # Headless + tunnel"
      } />

      <InfoBox color={C.green} label="Ships with Sane Defaults">
        <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>
          If config/luna.launch.json does not exist, the launcher uses hardcoded defaults
          (backend:8000, frontend:5173, observatory:8100, tunnel:off). First run works without any config file.
          The UI creates the file when you save.
        </div>
      </InfoBox>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 3: CLI Spec
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function CLISpecTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <CodeBlock title="launch_luna.sh -- rewritten CLI" code={
"#!/bin/bash\n" +
"# launch_luna.sh -- Luna Engine Launcher\n" +
"#\n" +
"# Reads config from config/luna.launch.json\n" +
"# Accepts CLI overrides for one-off changes\n" +
"# Launches all enabled services with health checks\n" +
"#\n" +
"# Usage:\n" +
"#   ./scripts/launch_luna.sh                    # Default profile\n" +
"#   ./scripts/launch_luna.sh --profile full     # All services\n" +
"#   ./scripts/launch_luna.sh --backend-port 9000\n" +
"#   ./scripts/launch_luna.sh --no-frontend --tunnel\n" +
"#   ./scripts/launch_luna.sh --status           # Show running services\n" +
"#   ./scripts/launch_luna.sh --stop             # Stop all Luna services\n" +
"#\n" +
"# FLAGS:\n" +
"# --backend-port PORT      Override backend port\n" +
"# --frontend-port PORT     Override frontend port\n" +
"# --observatory-port PORT  Override observatory port\n" +
"# --profile NAME           Use a named profile from config\n" +
"# --tunnel / --no-tunnel   Enable/disable tunnel\n" +
"# --observatory             Enable observatory\n" +
"# --no-frontend             Disable frontend\n" +
"# --no-backend              Disable backend (unusual but valid)\n" +
"# --debug                   Enable debug logging on backend\n" +
"# --status                  Show current running services and exit\n" +
"# --stop                    Kill all Luna processes and exit\n" +
"# --dry-run                 Show what would launch without starting"
      } />

      <CodeBlock title="Pre-flight check output" code={
"$ ./scripts/launch_luna.sh --profile full --dry-run\n\n" +
"Luna Engine Launcher -- Pre-flight Check\n" +
"========================================\n\n" +
"Config: config/luna.launch.json (profile: full)\n\n" +
"Services:\n" +
"  OK Backend     :8000  (port available)\n" +
"  OK Frontend    :5173  (port available)\n" +
"  XX Observatory :8100  (port in use -- PID 54321, python3)\n" +
"  OK Tunnel      cloudflared found\n\n" +
"Dependencies:\n" +
"  OK python3     Python 3.12.0\n" +
"  OK node        v20.10.0\n" +
"  OK cloudflared 2024.12.1\n\n" +
"Would launch: backend:8000, frontend:5173, tunnel\n" +
"Skipped: observatory:8100 (port conflict)\n\n" +
"[DRY RUN -- no services started]"
      } />

      <CodeBlock title="Status command" code={
"$ ./scripts/launch_luna.sh --status\n\n" +
"Luna Engine -- Running Services\n" +
"===============================\n\n" +
"* Backend     :8000  PID 12345  (uptime: 2h 14m)\n" +
"* Frontend    :5173  PID 12346  (uptime: 2h 14m)\n" +
"- Observatory :8100  (not running)\n" +
"* Tunnel      https://luna-abc123.trycloudflare.com\n\n" +
"Ctrl+C or --stop to shut down."
      } />

      <CodeBlock title="Stop command" code={
"$ ./scripts/launch_luna.sh --stop\n\n" +
"Stopping Luna services...\n" +
"  Killed backend     (PID 12345)\n" +
"  Killed frontend    (PID 12346)\n" +
"  Killed tunnel      (PID 12348)\n" +
"  Restored Apps Script sidebar URL to localhost\n\n" +
"All services stopped."
      } />

      <InfoBox color={C.warm} label="PID Tracking">
        <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>
          The launcher writes PIDs to /tmp/luna_launcher.pids (JSON).
          The --stop and --status commands read from this file.
          Stale PIDs (process no longer running) are cleaned automatically.
        </div>
      </InfoBox>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 4: Wiring
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function WiringTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>
        The hard part is not the launcher -- it is making everything downstream accept dynamic ports.
        Here is every place that needs to change.
      </div>

      <CodeBlock title="vite.config.js -- read ports from env vars" code={
"// vite.config.js (uses defineConfig + react plugin)\n\n" +
"// Read from env vars (set by launcher) or fall back to defaults\n" +
"const BACKEND_PORT = process.env.LUNA_BACKEND_PORT || 8000;\n" +
"const OBS_PORT = process.env.LUNA_OBSERVATORY_PORT || 8100;\n\n" +
"const backendTarget = 'http://localhost:' + BACKEND_PORT;\n" +
"const obsTarget = 'http://localhost:' + OBS_PORT;\n\n" +
"export default defineConfig({\n" +
"  plugins: [react()],\n" +
"  server: {\n" +
"    port: parseInt(process.env.LUNA_FRONTEND_PORT || 5173),\n" +
"    proxy: {\n" +
"      '/api': {\n" +
"        target: backendTarget,\n" +
"        changeOrigin: true,\n" +
"        rewrite: (path) => path.replace(/^\\/api/, '')\n" +
"      },\n" +
"      '/kozmo':        { target: backendTarget, changeOrigin: true, ws: true },\n" +
"      '/kozmo-assets': { target: backendTarget, changeOrigin: true },\n" +
"      '/project':      { target: backendTarget, changeOrigin: true },\n" +
"      '/eden':         { target: backendTarget, changeOrigin: true },\n" +
"      '/observatory': {\n" +
"        target: obsTarget,\n" +
"        changeOrigin: true,\n" +
"        ws: true,\n" +
"        rewrite: (path) => path.replace(/^\\/observatory/, ''),\n" +
"      },\n" +
"      '/persona': { target: backendTarget, changeOrigin: true },\n" +
"      '/hub':     { target: backendTarget, changeOrigin: true },\n" +
"      '/abort':   { target: backendTarget, changeOrigin: true },\n" +
"    }\n" +
"  }\n" +
"})"
      } />

      <CodeBlock title="launch_luna.sh -- config reader (uses python to parse JSON)" code={
"read_config() {\n" +
"  local config_file=\"$ROOT/config/luna.launch.json\"\n" +
"  \n" +
"  if [ ! -f \"$config_file\" ]; then\n" +
"    echo \"No config file found, using defaults\"\n" +
"    return\n" +
"  fi\n" +
"  \n" +
"  # Use Python to parse JSON into shell variables\n" +
"  eval \"$(python3 -c \"\n" +
"import json\n" +
"with open('$config_file') as f:\n" +
"    cfg = json.load(f)\n" +
"\n" +
"# Apply profile if specified\n" +
"profile = '$PROFILE' or 'default'\n" +
"if profile in cfg.get('profiles', {}):\n" +
"    import copy\n" +
"    merged = copy.deepcopy(cfg['services'])\n" +
"    for svc, overrides in cfg['profiles'][profile]['services'].items():\n" +
"        if svc in merged:\n" +
"            merged[svc].update(overrides)\n" +
"    services = merged\n" +
"else:\n" +
"    services = cfg['services']\n" +
"\n" +
"for svc, settings in services.items():\n" +
"    prefix = svc.upper()\n" +
"    for key, val in settings.items():\n" +
"        if isinstance(val, bool):\n" +
"            val = 'true' if val else 'false'\n" +
"        print(f'{prefix}_{key.upper()}={val}')\n" +
"\")\"\n" +
"}"
      } />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <InfoBox color={C.red} label="Hardcoded Ports Being Replaced">
          <div style={{ fontFamily: fontMono, fontSize: 12, color: C.textMuted, lineHeight: 2 }}>
            vite.config.js: 8 proxy routes to :8000<br/>
            vite.config.js: 1 observatory proxy to :8100<br/>
            launch_luna.sh: PORT=8000<br/>
            vite server.port: 5173
          </div>
        </InfoBox>
        <InfoBox color={C.green} label="Already Dynamic">
          <div style={{ fontFamily: fontMono, fontSize: 12, color: C.textMuted, lineHeight: 2 }}>
            run.py: already has --port flag<br/>
            frontend src: relative URLs only<br/>
            observatory: has --port support<br/>
            cloudflared: takes --url arg
          </div>
        </InfoBox>
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 5: Files & Tests
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function FilesTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{
        background: C.surface, borderRadius: 10, padding: 20, border: "1px solid " + C.border,
      }}>
        <div style={{ fontSize: 13, color: C.text, fontWeight: 600, marginBottom: 12 }}>File Manifest</div>
        <div style={{ fontFamily: fontMono, fontSize: 12, color: C.textMuted, lineHeight: 2.2 }}>
          {[
            ["config/luna.launch.json", "NEW", "~40 lines -- service config + profiles"],
            ["scripts/launch_luna.sh", "REWRITE", "~250 lines -- full launcher with config reader, pre-flight, PID tracking"],
            ["scripts/luna_launcher.html", "NEW", "~200 lines -- standalone config UI (open in browser)"],
            ["frontend/vite.config.js", "MODIFY", "~10 line change -- read ports from env vars"],
          ].map(function(item, i) {
            var color = item[1] === "NEW" ? C.green : item[1] === "REWRITE" ? C.warm : C.blue;
            return (
              <div key={i}>
                <span style={{ color: color }}>{item[1]}</span>{" "}
                <span style={{ color: C.text }}>{item[0]}</span><br/>
                <span style={{ color: C.textDim }}>{"  " + item[2]}</span>
              </div>
            );
          })}
        </div>
      </div>

      <CodeBlock title="Test: Port conflict detection" code={
"# Test that launcher detects occupied ports\n" +
"test_port_conflict() {\n" +
"  # Start a dummy server on 8000\n" +
"  python3 -m http.server 8000 &\n" +
"  DUMMY_PID=$!\n" +
"  sleep 1\n" +
"  \n" +
"  # Run pre-flight -- should detect conflict\n" +
"  output=$(./scripts/launch_luna.sh --dry-run 2>&1)\n" +
"  echo \"$output\" | grep -q \"port in use\"\n" +
"  assertEquals 0 $?\n" +
"  \n" +
"  kill $DUMMY_PID\n" +
"}"
      } />

      <CodeBlock title="Test: Config precedence" code={
"# Test that CLI flags override config file\n" +
"test_cli_override() {\n" +
"  # Config says 8000\n" +
"  echo '{ \"services\": { \"backend\": { \"port\": 8000 } } }' > config/luna.launch.json\n" +
"  \n" +
"  # CLI says 9000\n" +
"  output=$(./scripts/launch_luna.sh --backend-port 9000 --dry-run 2>&1)\n" +
"  echo \"$output\" | grep -q \":9000\"\n" +
"  assertEquals 0 $?\n" +
"}"
      } />

      <CodeBlock title="Test: Profile loading" code={
"# Test that --profile applies service overrides\n" +
"test_profile() {\n" +
"  output=$(./scripts/launch_luna.sh --profile api-only --dry-run 2>&1)\n" +
"  echo \"$output\" | grep \"Frontend\" | grep -q \"disabled\"\n" +
"  assertEquals 0 $?\n" +
"  echo \"$output\" | grep \"Backend\" | grep -q \"available\"\n" +
"  assertEquals 0 $?\n" +
"}"
      } />

      <InfoBox color={C.accent} label="Success Criteria">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            "luna.launch.json exists with default config + 3 profiles",
            "launch_luna.sh reads config, accepts CLI overrides, launches services in order",
            "Pre-flight checks detect port conflicts and missing dependencies",
            "--status shows running services, --stop kills them, --dry-run previews",
            "PID tracking in /tmp/luna_launcher.pids",
            "vite.config.js reads LUNA_BACKEND_PORT and LUNA_OBSERVATORY_PORT from env",
            "Frontend still works with plain 'npm run dev' (defaults apply)",
            "Tunnel patches Apps Script sidebar URL",
            "Ctrl+C cleanup kills all services and restores sidebar URL",
            "luna_launcher.html opens in browser, reads/writes config, shows generated CLI command",
          ].map(function(criteria, i) {
            return (
              <div key={i} style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.5 }}>
                <span style={{ color: C.green, marginRight: 8 }}>{"[ ]"}</span>{criteria}
              </div>
            );
          })}
        </div>
      </InfoBox>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Main
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export default function LauncherSpec() {
  const [tab, setTab] = useState(0);

  var tabContent = [
    LauncherUITab,
    ArchitectureTab,
    ConfigFormatTab,
    CLISpecTab,
    WiringTab,
    FilesTab,
  ];

  var ActiveTab = tabContent[tab];

  return (
    <div style={{
      background: C.bg, color: C.text, fontFamily: fontBody, minHeight: "100vh", padding: 32,
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />

      <div style={{ marginBottom: 32 }}>
        <div style={{ fontSize: 11, color: C.accent, fontWeight: 600, letterSpacing: 2, textTransform: "uppercase", marginBottom: 8 }}>
          Luna Engine v2.0 -- Architecture Spec
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, color: C.text, letterSpacing: -0.5 }}>
          App Launcher
        </div>
        <div style={{ fontSize: 15, color: C.textMuted, marginTop: 6 }}>
          One config file. One CLI. All services. Configurable ports with a UI that writes the config.
        </div>
      </div>

      <div style={{
        display: "flex", gap: 4, marginBottom: 28, borderBottom: "1px solid " + C.border, overflow: "auto",
      }}>
        {TABS.map(function(t, i) {
          return (
            <button key={i} onClick={function() { setTab(i); }} style={{
              background: "transparent",
              color: tab === i ? C.accent : C.textDim,
              border: "none",
              borderBottom: tab === i ? "2px solid " + C.accent : "2px solid transparent",
              padding: "10px 16px", fontSize: 13, fontWeight: tab === i ? 600 : 400,
              cursor: "pointer", fontFamily: fontBody, whiteSpace: "nowrap", transition: "all 0.15s",
            }}>
              {t}
            </button>
          );
        })}
      </div>

      <div style={{ maxWidth: 860 }}>
        <ActiveTab />
      </div>
    </div>
  );
}
