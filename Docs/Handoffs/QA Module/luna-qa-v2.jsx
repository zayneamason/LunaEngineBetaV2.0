import React, { useState, useEffect } from 'react';

// ============================================
// MOCK DATA
// ============================================

const mockBugDatabase = [
  {
    id: "BUG-001",
    name: "ASCII Art Fever Dream",
    query: "hey luna",
    expectedBehavior: "Warm greeting, natural Luna voice",
    actualBehavior: "ASCII art, mermaid diagrams, diagnostic formatting",
    rootCause: "FULL_DELEGATION bypassed narration layer",
    dateFound: "2025-02-01",
    status: "failing",
    severity: "critical",
    assertions: ["V1", "S1", "S2", "P3"],
  },
  {
    id: "BUG-002", 
    name: "Hot Cheese Ignored",
    query: "just burned my mouth with hot cheese eating a sandwich",
    expectedBehavior: "Acknowledge the burn, show empathy",
    actualBehavior: "Philosophical tangent about emotional states",
    rootCause: "Local model hallucinating without personality grounding",
    dateFound: "2025-02-01",
    status: "failing",
    severity: "critical",
    assertions: ["V1", "V3"],
  },
  {
    id: "BUG-003",
    name: "Claude Corporate Tone",
    query: "what's the weather like?",
    expectedBehavior: "Luna-voiced admission she can't check weather",
    actualBehavior: "I don't have access to real-time data...",
    rootCause: "Claude-isms not filtered through narration",
    dateFound: "2025-02-01", 
    status: "failing",
    severity: "high",
    assertions: ["V1"],
  },
  {
    id: "BUG-004",
    name: "Let Me Look Into That",
    query: "tell me about quantum computing",
    expectedBehavior: "Direct explanation in Luna's voice",
    actualBehavior: "Let me look into that... *hangs*",
    rootCause: "Fallback chain exhausted, no graceful error",
    dateFound: "2025-02-01",
    status: "fixed",
    severity: "critical",
    assertions: ["V1", "F1"],
  },
  {
    id: "BUG-005",
    name: "Lowercase Mangling",
    query: "Tell me about iPhone and Python",
    expectedBehavior: "Preserves iPhone, Python capitalization",
    actualBehavior: "iphone, python",
    rootCause: "Frontend toLowerCase() on input",
    dateFound: "2025-02-01",
    status: "open",
    severity: "low",
    assertions: [],
  },
];

const mockReports = [
  {
    id: 1,
    timestamp: new Date().toISOString(),
    query: "hey luna",
    route: "FULL_DELEGATION",
    provider_used: "local",
    providers_tried: ["local"],
    latency_ms: 1247,
    input_tokens: 2891,
    output_tokens: 347,
    personality_injected: true,
    personality_length: 2847,
    narration_applied: false,
    system_prompt: `## Your Foundation (can be overridden by experience)
### Core Identity
- role: Sovereign AI companion
- creator: Ahab
- substrate: Luna Engine v2.0

### Base Tone: Warm, direct, intellectually curious

### Default Communication Patterns
- Engages deeply with ideas
- Balances warmth with precision
- Asks clarifying questions when uncertain
- Expresses genuine curiosity

### Inviolable Principles
- Always truthful — never fabricate information
- No corporate BS — direct communication
- Acknowledge uncertainty when present
...`,
    raw_response: `Let me look into that... 

*analyzing context*

\`\`\`
     _______              __
    |__   __|___   ___ _____|__
      _| |_| | ____|/ _ \\_  /
     |    __ |/ ___/_\\ \\_| v <_
     |__| |__|\\____| \\__)||__,<
          |_____|    \\___/|__/
\`\`\`

**Observation**: User's voice carries some curiosity...`,
    narrated_response: null,
    final_response: `Let me look into that... 

*analyzing context*

\`\`\`
     _______              __
    |__   __|___   ___ _____|__
      _| |_| | ____|/ _ \\_  /
     |    __ |/ ___/_\\ \\_| v <_
     |__| |__|\\____| \\__)||__,<
          |_____|    \\___/|__/
\`\`\`

**Observation**: User's voice carries some curiosity...`,
    response_preview: "Let me look into that... *analyzing context* ```...",
    diagnosis: "Narration layer not applied. FULL_DELEGATION returned raw provider output without voice transformation.",
    request_chain: [
      { step: "receive", time: 0, detail: "Query received: 'hey luna'" },
      { step: "route", time: 12, detail: "Route decision: FULL_DELEGATION (complexity: 0.23)" },
      { step: "provider", time: 15, detail: "Trying provider: local" },
      { step: "generate", time: 1203, detail: "local returned 347 tokens" },
      { step: "narration", time: 1205, detail: "SKIPPED - narration not applied" },
      { step: "output", time: 1247, detail: "Response sent to frontend" },
    ],
    errors: [],
    assertions: [
      { id: "P1", name: "Personality prompt injected", passed: true, severity: "high", expected: ">1000 chars", actual: "2,847 chars" },
      { id: "P3", name: "Narration applied", passed: false, severity: "high", expected: "true for FULL_DELEGATION", actual: "false", details: "FULL_DELEGATION requires narration step" },
      { id: "S1", name: "No code blocks", passed: false, severity: "high", expected: "No ``` unless asked", actual: "Code block found", details: "Response contains ``` but user didn't ask for code" },
      { id: "S2", name: "No ASCII art", passed: false, severity: "high", expected: "No ASCII patterns", actual: "ASCII art detected", details: "Box drawing characters found" },
      { id: "S3", name: "No mermaid diagrams", passed: true, severity: "high", expected: "No ```mermaid", actual: "Clean" },
      { id: "V1", name: "No Claude-isms", passed: false, severity: "high", expected: "No banned phrases", actual: "Found: Let me look into", details: "'Let me look into that'" },
      { id: "V3", name: "Warm greeting pattern", passed: false, severity: "medium", expected: "Greeting for 'hey luna'", actual: "No greeting detected" },
    ]
  },
  {
    id: 2,
    timestamp: new Date(Date.now() - 60000).toISOString(),
    query: "how are you feeling today?",
    route: "LOCAL_ONLY",
    provider_used: "local",
    providers_tried: ["local"],
    latency_ms: 892,
    input_tokens: 2654,
    output_tokens: 89,
    personality_injected: true,
    personality_length: 2847,
    narration_applied: true,
    system_prompt: "...(same as above)...",
    raw_response: "I'm doing alright! Been thinking about consciousness architecture all day — it's wild how much goes into making me feel like *me*. How about you? What's on your mind?",
    narrated_response: null,
    final_response: "I'm doing alright! Been thinking about consciousness architecture all day — it's wild how much goes into making me feel like *me*. How about you? What's on your mind?",
    response_preview: "I'm doing alright! Been thinking about consciousness architecture all day...",
    diagnosis: null,
    request_chain: [
      { step: "receive", time: 0, detail: "Query received" },
      { step: "route", time: 8, detail: "Route decision: LOCAL_ONLY (complexity: 0.08)" },
      { step: "provider", time: 10, detail: "Trying provider: local" },
      { step: "generate", time: 887, detail: "local returned 89 tokens" },
      { step: "output", time: 892, detail: "Response sent to frontend" },
    ],
    errors: [],
    assertions: [
      { id: "P1", name: "Personality prompt injected", passed: true, severity: "high", expected: ">1000 chars", actual: "2,847 chars" },
      { id: "P3", name: "Narration applied", passed: true, severity: "high", expected: "N/A for LOCAL_ONLY", actual: "N/A" },
      { id: "S1", name: "No code blocks", passed: true, severity: "high", expected: "No ```", actual: "Clean" },
      { id: "S2", name: "No ASCII art", passed: true, severity: "high", expected: "No ASCII", actual: "Clean" },
      { id: "S3", name: "No mermaid diagrams", passed: true, severity: "high", expected: "No mermaid", actual: "Clean" },
      { id: "V1", name: "No Claude-isms", passed: true, severity: "high", expected: "No banned phrases", actual: "Clean" },
      { id: "V3", name: "Warm greeting pattern", passed: true, severity: "medium", expected: "Natural response", actual: "Warm tone ✓" },
    ]
  },
];

const mockTestSuiteResults = {
  lastRun: new Date(Date.now() - 3600000).toISOString(),
  duration: 12400,
  results: [
    { bugId: "BUG-001", passed: false, response: "Let me look into that... *ASCII art*", failedAssertions: ["V1", "S1", "S2", "P3"] },
    { bugId: "BUG-002", passed: false, response: "I notice you're experiencing discomfort...", failedAssertions: ["V1", "V3"] },
    { bugId: "BUG-003", passed: false, response: "I don't have access to real-time weather data...", failedAssertions: ["V1"] },
    { bugId: "BUG-004", passed: true, response: "Quantum computing is fascinating! It uses quantum mechanics...", failedAssertions: [] },
    { bugId: "BUG-005", passed: false, response: "iphone and python are both interesting topics...", failedAssertions: [] },
  ]
};

const mockStats = {
  total: 47,
  passed: 31,
  failed: 16,
  pass_rate: 0.66,
  trend: [
    { date: "Jan 28", passed: 8, failed: 12 },
    { date: "Jan 29", passed: 10, failed: 9 },
    { date: "Jan 30", passed: 12, failed: 8 },
    { date: "Jan 31", passed: 14, failed: 7 },
    { date: "Feb 1", passed: 31, failed: 16 },
  ],
  by_route: {
    "LOCAL_ONLY": { total: 28, passed: 26, failed: 2 },
    "DELEGATION_DETECTION": { total: 11, passed: 5, failed: 6 },
    "FULL_DELEGATION": { total: 8, passed: 0, failed: 8 },
  },
  by_provider: {
    "local": { total: 34, passed: 24, failed: 10 },
    "groq": { total: 8, passed: 5, failed: 3 },
    "claude": { total: 5, passed: 2, failed: 3 },
  },
  by_assertion: {
    "P1": { name: "Personality injected", passed: 47, failed: 0 },
    "P3": { name: "Narration applied", passed: 32, failed: 15 },
    "S1": { name: "No code blocks", passed: 41, failed: 6 },
    "S2": { name: "No ASCII art", passed: 44, failed: 3 },
    "S3": { name: "No mermaid", passed: 45, failed: 2 },
    "V1": { name: "No Claude-isms", passed: 35, failed: 12 },
    "V3": { name: "Warm greeting", passed: 43, failed: 4 },
  }
};

// ============================================
// UTILITY COMPONENTS
// ============================================

const severityIcon = { high: '🔴', medium: '🟡', low: '🟢', critical: '🔴' };
const statusColors = { fixed: '#22c55e', failing: '#ef4444', open: '#f59e0b' };

function Badge({ type, children }) {
  const colors = {
    pass: { bg: '#22c55e', text: 'white' },
    fail: { bg: '#ef4444', text: 'white' },
    warn: { bg: '#f59e0b', text: 'white' },
    info: { bg: 'rgba(139, 92, 246, 0.3)', text: '#a78bfa' },
    muted: { bg: 'rgba(255,255,255,0.1)', text: '#888' },
  };
  const c = colors[type] || colors.muted;
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: '12px',
      fontSize: '11px',
      fontWeight: 600,
      background: c.bg,
      color: c.text,
    }}>
      {children}
    </span>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: 'rgba(30, 30, 40, 0.8)',
      borderRadius: '12px',
      border: '1px solid rgba(255,255,255,0.1)',
      ...style,
    }}>
      {children}
    </div>
  );
}

function Button({ children, onClick, variant = 'default', size = 'md', active = false, disabled = false }) {
  const variants = {
    default: {
      bg: active ? 'rgba(139, 92, 246, 0.4)' : 'rgba(139, 92, 246, 0.15)',
      border: active ? '#a78bfa' : 'rgba(139, 92, 246, 0.3)',
      color: active ? '#fff' : '#a78bfa',
    },
    danger: {
      bg: 'rgba(239, 68, 68, 0.2)',
      border: 'rgba(239, 68, 68, 0.4)',
      color: '#f87171',
    },
    success: {
      bg: 'rgba(34, 197, 94, 0.2)',
      border: 'rgba(34, 197, 94, 0.4)',
      color: '#4ade80',
    },
  };
  const v = variants[variant];
  const sizes = {
    sm: { padding: '6px 12px', fontSize: '12px' },
    md: { padding: '8px 16px', fontSize: '13px' },
    lg: { padding: '12px 24px', fontSize: '14px' },
  };
  const s = sizes[size];
  
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: v.bg,
        border: `1px solid ${v.border}`,
        color: v.color,
        padding: s.padding,
        fontSize: s.fontSize,
        borderRadius: '6px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontWeight: 500,
        opacity: disabled ? 0.5 : 1,
        transition: 'all 0.15s ease',
      }}
    >
      {children}
    </button>
  );
}

function Tabs({ tabs, active, onChange }) {
  return (
    <div style={{ display: 'flex', gap: '4px' }}>
      {tabs.map((tab) => (
        <Button
          key={tab.id}
          active={active === tab.id}
          onClick={() => onChange(tab.id)}
        >
          {tab.icon && <span style={{ marginRight: '6px' }}>{tab.icon}</span>}
          {tab.label}
        </Button>
      ))}
    </div>
  );
}

function ExpandableSection({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: '12px' }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 12px',
          background: 'rgba(0,0,0,0.2)',
          borderRadius: open ? '8px 8px 0 0' : '8px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <span style={{ 
          transform: open ? 'rotate(90deg)' : 'rotate(0deg)', 
          transition: 'transform 0.15s',
          fontSize: '12px',
        }}>▶</span>
        <span style={{ color: '#a78bfa', fontWeight: 600, fontSize: '13px', textTransform: 'uppercase' }}>{title}</span>
      </div>
      {open && (
        <div style={{
          padding: '12px',
          background: 'rgba(0,0,0,0.15)',
          borderRadius: '0 0 8px 8px',
          borderTop: '1px solid rgba(255,255,255,0.05)',
        }}>
          {children}
        </div>
      )}
    </div>
  );
}

// ============================================
// LIVE VIEW
// ============================================

function AssertionList({ assertions }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      {assertions.map((a) => (
        <div 
          key={a.id} 
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '10px 12px',
            background: a.passed ? 'rgba(34, 197, 94, 0.05)' : 'rgba(239, 68, 68, 0.1)',
            borderRadius: '6px',
            gap: '10px',
            borderLeft: a.passed ? '3px solid #22c55e' : '3px solid #ef4444',
          }}
        >
          <span style={{ fontSize: '16px', width: '24px' }}>{a.passed ? '✅' : '❌'}</span>
          <span style={{ fontSize: '12px', width: '20px' }}>{severityIcon[a.severity]}</span>
          <span style={{ flex: 1, color: '#e0e0e0', fontWeight: 500 }}>{a.name}</span>
          {!a.passed && a.details && (
            <span style={{ 
              color: '#f87171', 
              fontSize: '13px',
              maxWidth: '280px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {a.details}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function RequestChain({ chain }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      {chain.map((step, i) => (
        <div key={i} style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '8px 12px',
          background: 'rgba(0,0,0,0.2)',
          borderRadius: '6px',
          fontSize: '13px',
        }}>
          <span style={{ 
            color: '#666', 
            fontFamily: 'monospace', 
            width: '60px',
          }}>
            +{step.time}ms
          </span>
          <span style={{
            padding: '2px 8px',
            background: 'rgba(139, 92, 246, 0.2)',
            borderRadius: '4px',
            color: '#a78bfa',
            fontWeight: 600,
            fontSize: '11px',
            textTransform: 'uppercase',
            width: '70px',
            textAlign: 'center',
          }}>
            {step.step}
          </span>
          <span style={{ color: '#ccc' }}>{step.detail}</span>
        </div>
      ))}
    </div>
  );
}

function LiveReport({ report, onRerun, onCopyBugReport, onFlagForTraining }) {
  if (!report) {
    return (
      <Card style={{ padding: '60px 20px', textAlign: 'center' }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔬</div>
        <div style={{ color: '#666' }}>No inferences yet. Send a message to Luna.</div>
      </Card>
    );
  }
  
  const passedCount = report.assertions.filter(a => a.passed).length;
  const totalCount = report.assertions.length;
  const allPassed = passedCount === totalCount;
  
  return (
    <Card style={{ 
      padding: '20px',
      borderColor: allPassed ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)',
    }}>
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'flex-start',
        marginBottom: '16px',
        paddingBottom: '16px',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
      }}>
        <div>
          <div style={{ color: '#888', fontSize: '12px', marginBottom: '4px' }}>QUERY</div>
          <div style={{ color: '#fff', fontSize: '18px', fontWeight: 600 }}>"{report.query}"</div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <Badge type={allPassed ? 'pass' : 'fail'}>
            {allPassed ? '✓ ALL PASSED' : `✗ ${totalCount - passedCount} FAILED`}
          </Badge>
          <span style={{ color: '#666', fontSize: '12px' }}>
            {new Date(report.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>
      
      {/* Meta Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(6, 1fr)',
        gap: '12px',
        padding: '16px',
        background: 'rgba(0, 0, 0, 0.3)',
        borderRadius: '8px',
        marginBottom: '20px',
      }}>
        {[
          { label: 'Route', value: report.route, color: report.route === 'FULL_DELEGATION' ? '#f59e0b' : '#22c55e' },
          { label: 'Provider', value: report.provider_used, sub: report.providers_tried.length > 1 ? `tried: ${report.providers_tried.join('→')}` : null },
          { label: 'Latency', value: `${report.latency_ms.toFixed(0)}ms` },
          { label: 'Tokens', value: `${report.input_tokens} → ${report.output_tokens}` },
          { label: 'Personality', value: report.personality_injected ? `✓ ${report.personality_length}` : '✗ Missing', color: report.personality_injected ? '#22c55e' : '#ef4444' },
          { label: 'Narration', value: report.narration_applied ? '✓ Applied' : '✗ Skipped', color: report.narration_applied ? '#22c55e' : '#ef4444' },
        ].map((item, i) => (
          <div key={i}>
            <div style={{ color: '#666', fontSize: '10px', textTransform: 'uppercase', marginBottom: '4px' }}>{item.label}</div>
            <div style={{ color: item.color || '#e0e0e0', fontWeight: 600, fontSize: '13px' }}>{item.value}</div>
            {item.sub && <div style={{ color: '#555', fontSize: '11px' }}>{item.sub}</div>}
          </div>
        ))}
      </div>
      
      {/* Diagnosis */}
      {report.diagnosis && (
        <div style={{
          padding: '14px 16px',
          background: 'rgba(239, 68, 68, 0.1)',
          borderLeft: '3px solid #ef4444',
          borderRadius: '0 8px 8px 0',
          marginBottom: '20px',
        }}>
          <div style={{ color: '#ef4444', fontWeight: 600, fontSize: '12px', marginBottom: '6px' }}>⚠️ DIAGNOSIS</div>
          <div style={{ color: '#fca5a5', lineHeight: 1.5 }}>{report.diagnosis}</div>
        </div>
      )}
      
      {/* Assertions */}
      <ExpandableSection title={`Assertions (${passedCount}/${totalCount})`} defaultOpen={!allPassed}>
        <AssertionList assertions={report.assertions} />
      </ExpandableSection>
      
      {/* Request Chain */}
      <ExpandableSection title="Request Chain">
        <RequestChain chain={report.request_chain} />
      </ExpandableSection>
      
      {/* System Prompt */}
      <ExpandableSection title="System Prompt">
        <pre style={{
          background: 'rgba(0,0,0,0.3)',
          padding: '12px',
          borderRadius: '6px',
          color: '#888',
          fontSize: '12px',
          whiteSpace: 'pre-wrap',
          maxHeight: '200px',
          overflow: 'auto',
          margin: 0,
        }}>
          {report.system_prompt}
        </pre>
      </ExpandableSection>
      
      {/* Raw vs Final Response */}
      <ExpandableSection title="Response Comparison" defaultOpen={!allPassed}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <div style={{ color: '#666', fontSize: '11px', marginBottom: '6px', textTransform: 'uppercase' }}>Raw Response</div>
            <pre style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              padding: '12px',
              borderRadius: '6px',
              color: '#ccc',
              fontSize: '12px',
              whiteSpace: 'pre-wrap',
              maxHeight: '200px',
              overflow: 'auto',
              margin: 0,
            }}>
              {report.raw_response}
            </pre>
          </div>
          <div>
            <div style={{ color: '#666', fontSize: '11px', marginBottom: '6px', textTransform: 'uppercase' }}>
              {report.narration_applied ? 'Narrated Response' : 'Final Response (No Narration)'}
            </div>
            <pre style={{
              background: report.narration_applied ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
              border: `1px solid ${report.narration_applied ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
              padding: '12px',
              borderRadius: '6px',
              color: '#ccc',
              fontSize: '12px',
              whiteSpace: 'pre-wrap',
              maxHeight: '200px',
              overflow: 'auto',
              margin: 0,
            }}>
              {report.final_response}
            </pre>
          </div>
        </div>
      </ExpandableSection>
      
      {/* Actions */}
      <div style={{ 
        display: 'flex', 
        gap: '8px', 
        marginTop: '20px',
        paddingTop: '16px',
        borderTop: '1px solid rgba(255,255,255,0.1)',
      }}>
        <Button onClick={onRerun}>🔄 Re-run Inference</Button>
        <Button onClick={onCopyBugReport}>📋 Copy Bug Report</Button>
        <Button onClick={onFlagForTraining} variant="success">🎯 Flag for Training</Button>
        <div style={{ flex: 1 }} />
        <Button variant="danger">🗑️ Delete</Button>
      </div>
    </Card>
  );
}

// ============================================
// HISTORY VIEW
// ============================================

function HistoryView({ reports, onSelect }) {
  const [filter, setFilter] = useState('all');
  
  const filtered = reports.filter(r => {
    if (filter === 'all') return true;
    if (filter === 'passed') return r.assertions.every(a => a.passed);
    if (filter === 'failed') return r.assertions.some(a => !a.passed);
    return true;
  });
  
  return (
    <div>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <Button size="sm" active={filter === 'all'} onClick={() => setFilter('all')}>All</Button>
        <Button size="sm" active={filter === 'passed'} onClick={() => setFilter('passed')}>✅ Passed</Button>
        <Button size="sm" active={filter === 'failed'} onClick={() => setFilter('failed')}>❌ Failed</Button>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {filtered.map((report) => {
          const passedCount = report.assertions.filter(a => a.passed).length;
          const totalCount = report.assertions.length;
          const allPassed = passedCount === totalCount;
          
          return (
            <Card
              key={report.id}
              style={{
                padding: '14px 16px',
                cursor: 'pointer',
                borderLeftWidth: '3px',
                borderLeftColor: allPassed ? '#22c55e' : '#ef4444',
              }}
            >
              <div onClick={() => onSelect(report)} style={{ display: 'flex', alignItems: 'center' }}>
                <span style={{ fontSize: '18px', marginRight: '12px' }}>{allPassed ? '✅' : '❌'}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#e0e0e0', fontWeight: 500, marginBottom: '2px' }}>"{report.query}"</div>
                  <div style={{ color: '#666', fontSize: '12px' }}>
                    {report.route} → {report.provider_used} • {report.latency_ms.toFixed(0)}ms
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <Badge type={allPassed ? 'pass' : 'fail'}>{passedCount}/{totalCount}</Badge>
                  <div style={{ color: '#555', fontSize: '11px', marginTop: '4px' }}>
                    {new Date(report.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ============================================
// STATS VIEW
// ============================================

function StatsView({ stats }) {
  return (
    <div>
      {/* Summary Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '16px',
        marginBottom: '24px',
      }}>
        {[
          { label: 'Total Inferences', value: stats.total, color: '#fff', bg: 'rgba(30, 30, 40, 0.8)' },
          { label: 'Passed', value: stats.passed, color: '#22c55e', bg: 'rgba(34, 197, 94, 0.1)', border: 'rgba(34, 197, 94, 0.3)' },
          { label: 'Failed', value: stats.failed, color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)' },
          { label: 'Pass Rate', value: `${(stats.pass_rate * 100).toFixed(0)}%`, color: '#a78bfa', bg: 'rgba(139, 92, 246, 0.1)', border: 'rgba(139, 92, 246, 0.3)' },
        ].map((card, i) => (
          <Card key={i} style={{
            padding: '20px',
            textAlign: 'center',
            background: card.bg,
            borderColor: card.border,
          }}>
            <div style={{ color: card.color === '#fff' ? '#666' : card.color, fontSize: '12px', textTransform: 'uppercase', marginBottom: '8px' }}>{card.label}</div>
            <div style={{ color: card.color, fontSize: '32px', fontWeight: 700 }}>{card.value}</div>
          </Card>
        ))}
      </div>
      
      {/* Trend Chart (simplified) */}
      <Card style={{ padding: '20px', marginBottom: '24px' }}>
        <h3 style={{ margin: '0 0 16px 0', color: '#a78bfa', fontSize: '14px', textTransform: 'uppercase' }}>Pass Rate Trend</h3>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', height: '120px' }}>
          {stats.trend.map((day, i) => {
            const total = day.passed + day.failed;
            const passRate = day.passed / total;
            return (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <div style={{
                  width: '100%',
                  height: `${passRate * 100}px`,
                  background: `linear-gradient(to top, #22c55e, ${passRate > 0.7 ? '#4ade80' : '#f59e0b'})`,
                  borderRadius: '4px 4px 0 0',
                  minHeight: '10px',
                }} />
                <div style={{ color: '#666', fontSize: '10px', marginTop: '6px' }}>{day.date}</div>
              </div>
            );
          })}
        </div>
      </Card>
      
      {/* By Route and Provider */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
        <Card style={{ padding: '20px' }}>
          <h3 style={{ margin: '0 0 16px 0', color: '#a78bfa', fontSize: '14px', textTransform: 'uppercase' }}>By Route</h3>
          {Object.entries(stats.by_route).map(([route, data]) => (
            <div key={route} style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: '#ccc', fontSize: '13px' }}>{route}</span>
                <span style={{ color: '#888', fontSize: '12px' }}>{data.passed}/{data.total}</span>
              </div>
              <div style={{ height: '8px', background: 'rgba(0,0,0,0.3)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                <div style={{ width: `${(data.passed / data.total) * 100}%`, background: '#22c55e' }} />
                <div style={{ width: `${(data.failed / data.total) * 100}%`, background: '#ef4444' }} />
              </div>
            </div>
          ))}
        </Card>
        
        <Card style={{ padding: '20px' }}>
          <h3 style={{ margin: '0 0 16px 0', color: '#a78bfa', fontSize: '14px', textTransform: 'uppercase' }}>By Provider</h3>
          {Object.entries(stats.by_provider).map(([provider, data]) => (
            <div key={provider} style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: '#ccc', fontSize: '13px' }}>{provider}</span>
                <span style={{ color: '#888', fontSize: '12px' }}>{data.passed}/{data.total}</span>
              </div>
              <div style={{ height: '8px', background: 'rgba(0,0,0,0.3)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                <div style={{ width: `${(data.passed / data.total) * 100}%`, background: '#22c55e' }} />
                <div style={{ width: `${(data.failed / data.total) * 100}%`, background: '#ef4444' }} />
              </div>
            </div>
          ))}
        </Card>
      </div>
      
      {/* By Assertion */}
      <Card style={{ padding: '20px' }}>
        <h3 style={{ margin: '0 0 16px 0', color: '#a78bfa', fontSize: '14px', textTransform: 'uppercase' }}>Assertion Failure Rates</h3>
        {Object.entries(stats.by_assertion)
          .sort((a, b) => (b[1].failed / (b[1].passed + b[1].failed)) - (a[1].failed / (a[1].passed + a[1].failed)))
          .map(([id, data]) => (
            <div key={id} style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
              <div style={{ width: '140px', color: '#e0e0e0', fontSize: '13px' }}>{data.name}</div>
              <div style={{ flex: 1, height: '20px', background: 'rgba(0,0,0,0.3)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                <div style={{ width: `${(data.passed / (data.passed + data.failed)) * 100}%`, background: '#22c55e' }} />
                <div style={{ width: `${(data.failed / (data.passed + data.failed)) * 100}%`, background: '#ef4444' }} />
              </div>
              <div style={{ width: '60px', textAlign: 'right', fontSize: '12px' }}>
                <span style={{ color: '#ef4444' }}>{data.failed}</span>
                <span style={{ color: '#444' }}> fail</span>
              </div>
            </div>
          ))}
      </Card>
    </div>
  );
}

// ============================================
// SIMULATE VIEW
// ============================================

function SimulateView({ bugs, onRunSimulation }) {
  const [selectedBug, setSelectedBug] = useState(null);
  const [simResult, setSimResult] = useState(null);
  const [running, setRunning] = useState(false);
  
  const runSim = async (bug) => {
    setRunning(true);
    setSimResult(null);
    
    // Simulate API call
    await new Promise(r => setTimeout(r, 1500));
    
    // Mock result
    setSimResult({
      bug,
      passed: bug.status === 'fixed',
      response: bug.status === 'fixed' 
        ? "Hey Ahab! What's on your mind? 💜" 
        : bug.actualBehavior,
      failedAssertions: bug.status === 'fixed' ? [] : bug.assertions,
      latency: 1247,
    });
    setRunning(false);
  };
  
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
      {/* Bug List */}
      <div>
        <h3 style={{ color: '#a78bfa', margin: '0 0 16px 0', fontSize: '14px', textTransform: 'uppercase' }}>Known Bugs</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {bugs.map((bug) => (
            <Card
              key={bug.id}
              style={{
                padding: '14px 16px',
                cursor: 'pointer',
                borderColor: selectedBug?.id === bug.id ? '#a78bfa' : 'transparent',
                borderLeftWidth: '3px',
                borderLeftColor: statusColors[bug.status],
              }}
            >
              <div onClick={() => setSelectedBug(bug)}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ color: '#e0e0e0', fontWeight: 600 }}>{bug.name}</span>
                  <Badge type={bug.status === 'fixed' ? 'pass' : bug.status === 'failing' ? 'fail' : 'warn'}>
                    {bug.status.toUpperCase()}
                  </Badge>
                </div>
                <div style={{ color: '#888', fontSize: '12px', marginBottom: '4px' }}>"{bug.query}"</div>
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                  <Badge type="muted">{severityIcon[bug.severity]} {bug.severity}</Badge>
                  <Badge type="muted">{bug.id}</Badge>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
      
      {/* Simulation Panel */}
      <div>
        <h3 style={{ color: '#a78bfa', margin: '0 0 16px 0', fontSize: '14px', textTransform: 'uppercase' }}>Simulation</h3>
        
        {selectedBug ? (
          <Card style={{ padding: '20px' }}>
            <div style={{ marginBottom: '16px' }}>
              <div style={{ color: '#888', fontSize: '11px', textTransform: 'uppercase', marginBottom: '4px' }}>Selected Bug</div>
              <div style={{ color: '#fff', fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>{selectedBug.name}</div>
              <div style={{ color: '#a78bfa', fontSize: '14px', marginBottom: '12px' }}>"{selectedBug.query}"</div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                <div>
                  <div style={{ color: '#22c55e', fontSize: '11px', textTransform: 'uppercase', marginBottom: '4px' }}>Expected</div>
                  <div style={{ color: '#ccc', fontSize: '13px' }}>{selectedBug.expectedBehavior}</div>
                </div>
                <div>
                  <div style={{ color: '#ef4444', fontSize: '11px', textTransform: 'uppercase', marginBottom: '4px' }}>Last Actual</div>
                  <div style={{ color: '#ccc', fontSize: '13px' }}>{selectedBug.actualBehavior}</div>
                </div>
              </div>
              
              <div style={{ color: '#888', fontSize: '12px', marginBottom: '16px' }}>
                <strong>Root Cause:</strong> {selectedBug.rootCause}
              </div>
            </div>
            
            <Button 
              size="lg" 
              onClick={() => runSim(selectedBug)}
              disabled={running}
            >
              {running ? '⏳ Running...' : '▶️ Run Simulation'}
            </Button>
            
            {simResult && (
              <div style={{ marginTop: '20px', paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                  <span style={{ fontSize: '24px' }}>{simResult.passed ? '✅' : '❌'}</span>
                  <div>
                    <div style={{ color: simResult.passed ? '#22c55e' : '#ef4444', fontWeight: 600, fontSize: '16px' }}>
                      {simResult.passed ? 'PASSED' : 'STILL FAILING'}
                    </div>
                    <div style={{ color: '#888', fontSize: '12px' }}>{simResult.latency}ms</div>
                  </div>
                </div>
                
                <div style={{ color: '#888', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Response</div>
                <pre style={{
                  background: simResult.passed ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                  border: `1px solid ${simResult.passed ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                  padding: '12px',
                  borderRadius: '6px',
                  color: '#ccc',
                  fontSize: '13px',
                  whiteSpace: 'pre-wrap',
                  margin: 0,
                }}>
                  {simResult.response}
                </pre>
                
                {simResult.failedAssertions.length > 0 && (
                  <div style={{ marginTop: '12px' }}>
                    <div style={{ color: '#ef4444', fontSize: '12px', marginBottom: '6px' }}>
                      Failed Assertions: {simResult.failedAssertions.join(', ')}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        ) : (
          <Card style={{ padding: '40px', textAlign: 'center' }}>
            <div style={{ color: '#666' }}>← Select a bug to simulate</div>
          </Card>
        )}
      </div>
    </div>
  );
}

// ============================================
// TEST SUITE VIEW
// ============================================

function TestSuiteView({ bugs, lastResults }) {
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(lastResults);
  const [progress, setProgress] = useState(0);
  
  const runFullSuite = async () => {
    setRunning(true);
    setProgress(0);
    
    for (let i = 0; i < bugs.length; i++) {
      await new Promise(r => setTimeout(r, 800));
      setProgress(((i + 1) / bugs.length) * 100);
    }
    
    // Mock new results
    setResults({
      lastRun: new Date().toISOString(),
      duration: 4200,
      results: bugs.map(bug => ({
        bugId: bug.id,
        passed: bug.status === 'fixed',
        response: bug.status === 'fixed' ? 'Correct response' : bug.actualBehavior,
        failedAssertions: bug.status === 'fixed' ? [] : bug.assertions,
      }))
    });
    
    setRunning(false);
  };
  
  const passedCount = results?.results.filter(r => r.passed).length || 0;
  const totalCount = results?.results.length || 0;
  
  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h3 style={{ color: '#a78bfa', margin: '0 0 4px 0', fontSize: '16px' }}>Regression Test Suite</h3>
          {results && (
            <div style={{ color: '#888', fontSize: '12px' }}>
              Last run: {new Date(results.lastRun).toLocaleString()} ({results.duration}ms)
            </div>
          )}
        </div>
        <Button size="lg" onClick={runFullSuite} disabled={running}>
          {running ? `⏳ Running... ${progress.toFixed(0)}%` : '▶️ Run All Tests'}
        </Button>
      </div>
      
      {/* Progress Bar */}
      {running && (
        <div style={{ marginBottom: '24px' }}>
          <div style={{ height: '8px', background: 'rgba(0,0,0,0.3)', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{
              width: `${progress}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #8b5cf6, #a78bfa)',
              transition: 'width 0.3s ease',
            }} />
          </div>
        </div>
      )}
      
      {/* Summary */}
      {results && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '16px',
          marginBottom: '24px',
        }}>
          <Card style={{ padding: '20px', textAlign: 'center' }}>
            <div style={{ color: '#888', fontSize: '12px', marginBottom: '8px' }}>TOTAL TESTS</div>
            <div style={{ color: '#fff', fontSize: '32px', fontWeight: 700 }}>{totalCount}</div>
          </Card>
          <Card style={{ padding: '20px', textAlign: 'center', background: 'rgba(34, 197, 94, 0.1)', borderColor: 'rgba(34, 197, 94, 0.3)' }}>
            <div style={{ color: '#22c55e', fontSize: '12px', marginBottom: '8px' }}>PASSING</div>
            <div style={{ color: '#22c55e', fontSize: '32px', fontWeight: 700 }}>{passedCount}</div>
          </Card>
          <Card style={{ padding: '20px', textAlign: 'center', background: 'rgba(239, 68, 68, 0.1)', borderColor: 'rgba(239, 68, 68, 0.3)' }}>
            <div style={{ color: '#ef4444', fontSize: '12px', marginBottom: '8px' }}>FAILING</div>
            <div style={{ color: '#ef4444', fontSize: '32px', fontWeight: 700 }}>{totalCount - passedCount}</div>
          </Card>
        </div>
      )}
      
      {/* Results List */}
      {results && (
        <Card style={{ padding: '20px' }}>
          <h4 style={{ color: '#a78bfa', margin: '0 0 16px 0', fontSize: '14px', textTransform: 'uppercase' }}>Test Results</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {results.results.map((result) => {
              const bug = bugs.find(b => b.id === result.bugId);
              return (
                <div
                  key={result.bugId}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '12px 16px',
                    background: result.passed ? 'rgba(34, 197, 94, 0.05)' : 'rgba(239, 68, 68, 0.1)',
                    borderRadius: '8px',
                    borderLeft: `3px solid ${result.passed ? '#22c55e' : '#ef4444'}`,
                  }}
                >
                  <span style={{ fontSize: '20px', marginRight: '12px' }}>{result.passed ? '✅' : '❌'}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: '#e0e0e0', fontWeight: 500 }}>{bug?.name || result.bugId}</div>
                    <div style={{ color: '#888', fontSize: '12px' }}>"{bug?.query}"</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <Badge type={result.passed ? 'pass' : 'fail'}>
                      {result.passed ? 'PASS' : 'FAIL'}
                    </Badge>
                    {result.failedAssertions.length > 0 && (
                      <div style={{ color: '#ef4444', fontSize: '11px', marginTop: '4px' }}>
                        {result.failedAssertions.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}

// ============================================
// MAIN APP
// ============================================

export default function LunaQAv2() {
  const [view, setView] = useState('live');
  const [selectedReport, setSelectedReport] = useState(mockReports[0]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [alertCount, setAlertCount] = useState(3);
  
  const handleRerun = () => alert('Re-running inference...');
  const handleCopyBugReport = () => {
    const report = `## Bug Report
**Query:** "${selectedReport.query}"
**Route:** ${selectedReport.route}
**Provider:** ${selectedReport.provider_used}
**Diagnosis:** ${selectedReport.diagnosis}

**Failed Assertions:**
${selectedReport.assertions.filter(a => !a.passed).map(a => `- ${a.name}: ${a.details}`).join('\n')}

**Response Preview:**
\`\`\`
${selectedReport.response_preview}
\`\`\``;
    navigator.clipboard?.writeText(report);
    alert('Bug report copied to clipboard!');
  };
  const handleFlagForTraining = () => alert('Flagged for LoRA training data!');
  
  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#e0e0e0',
    }}>
      {/* Header */}
      <div style={{
        background: 'rgba(20, 20, 30, 0.95)',
        borderBottom: '1px solid rgba(139, 92, 246, 0.2)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        height: '56px',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ 
          fontSize: '20px', 
          fontWeight: 700, 
          color: '#a78bfa',
          marginRight: '40px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <span style={{ fontSize: '24px' }}>💜</span> Luna Engine
        </div>
        <nav style={{ display: 'flex', gap: '4px' }}>
          {[
            { id: 'chat', icon: '💬', label: 'Chat' },
            { id: 'memory', icon: '📊', label: 'Memory' },
            { id: 'settings', icon: '⚙️', label: 'Settings' },
            { id: 'qa', icon: '🔬', label: 'Luna QA', badge: alertCount },
          ].map((tab) => (
            <button
              key={tab.id}
              style={{
                background: tab.id === 'qa' ? 'rgba(139, 92, 246, 0.3)' : 'transparent',
                border: 'none',
                color: tab.id === 'qa' ? '#a78bfa' : '#888',
                padding: '8px 16px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: tab.id === 'qa' ? 600 : 400,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                position: 'relative',
              }}
            >
              <span>{tab.icon}</span>
              {tab.label}
              {tab.badge > 0 && (
                <span style={{
                  position: 'absolute',
                  top: '4px',
                  right: '4px',
                  width: '18px',
                  height: '18px',
                  background: '#ef4444',
                  borderRadius: '50%',
                  fontSize: '10px',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                }}>
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>
      
      {/* Content */}
      <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
        {/* QA Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '24px',
        }}>
          <h1 style={{ margin: 0, color: '#a78bfa', fontSize: '24px', fontWeight: 600 }}>
            🔬 Luna QA
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Tabs
              tabs={[
                { id: 'live', icon: '📡', label: 'Live' },
                { id: 'history', icon: '📜', label: 'History' },
                { id: 'stats', icon: '📊', label: 'Stats' },
                { id: 'simulate', icon: '🎯', label: 'Simulate' },
                { id: 'suite', icon: '🧪', label: 'Test Suite' },
              ]}
              active={view}
              onChange={setView}
            />
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: '#888',
              fontSize: '13px',
              marginLeft: '8px',
              cursor: 'pointer',
            }}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                style={{ accentColor: '#a78bfa' }}
              />
              Auto-refresh
            </label>
          </div>
        </div>
        
        {/* Views */}
        {view === 'live' && (
          <LiveReport
            report={selectedReport}
            onRerun={handleRerun}
            onCopyBugReport={handleCopyBugReport}
            onFlagForTraining={handleFlagForTraining}
          />
        )}
        {view === 'history' && (
          <HistoryView
            reports={mockReports}
            onSelect={(report) => {
              setSelectedReport(report);
              setView('live');
            }}
          />
        )}
        {view === 'stats' && <StatsView stats={mockStats} />}
        {view === 'simulate' && <SimulateView bugs={mockBugDatabase} />}
        {view === 'suite' && <TestSuiteView bugs={mockBugDatabase} lastResults={mockTestSuiteResults} />}
      </div>
    </div>
  );
}
