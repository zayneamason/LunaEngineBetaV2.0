import React, { useState } from 'react';
import LLMSection from './sections/LLMSection';
import IdentitySection from './sections/IdentitySection';
import VoiceSection from './sections/VoiceSection';
import PersonalitySection from './sections/PersonalitySection';
import MemorySection from './sections/MemorySection';
import CollectionsSection from './sections/CollectionsSection';
import NetworkSection from './sections/NetworkSection';
import AboutSection from './sections/AboutSection';
import SkillsSection from './sections/SkillsSection';
import DisplaySection from './sections/DisplaySection';

const SECTIONS = [
  { id: 'llm',          label: 'LLM PROVIDERS' },
  { id: 'identity',     label: 'IDENTITY' },
  { id: 'voice',        label: 'VOICE' },
  { id: 'personality',  label: 'PERSONALITY' },
  { id: 'memory',       label: 'MEMORY' },
  { id: 'collections',  label: 'COLLECTIONS' },
  { id: 'skills',       label: 'SKILLS' },
  { id: 'display',      label: 'DISPLAY' },
  { id: 'network',      label: 'NETWORK' },
  { id: 'about',        label: 'ABOUT' },
];

const SECTION_COMPONENTS = {
  llm: LLMSection,
  identity: IdentitySection,
  voice: VoiceSection,
  personality: PersonalitySection,
  memory: MemorySection,
  collections: CollectionsSection,
  skills: SkillsSection,
  display: DisplaySection,
  network: NetworkSection,
  about: AboutSection,
};

export default function SettingsApp() {
  const [activeSection, setActiveSection] = useState('llm');
  const ActiveComponent = SECTION_COMPONENTS[activeSection];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '200px 1fr',
      position: 'absolute',
      inset: 0,
      overflow: 'hidden',
      background: 'var(--ec-bg)',
    }}>
      {/* Sidebar */}
      <nav style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        padding: '16px 8px',
        borderRight: '1px solid var(--ec-border)',
        background: 'var(--ec-bg-raised)',
        overflowY: 'auto',
      }}>
        {SECTIONS.map((s) => {
          const isActive = activeSection === s.id;
          return (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              className="ec-font-label"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 12px',
                border: 'none',
                borderLeft: isActive ? '2px solid var(--ec-text-soft)' : '2px solid transparent',
                background: isActive ? 'rgba(255,255,255,0.03)' : 'transparent',
                color: isActive ? 'var(--ec-text)' : 'var(--ec-text-faint)',
                fontSize: 9,
                letterSpacing: 1.5,
                cursor: 'pointer',
                textAlign: 'left',
                borderRadius: 0,
                transition: 'all 0.15s ease',
              }}
            >
              {s.label}
            </button>
          );
        })}
      </nav>

      {/* Content */}
      <div style={{
        overflowY: 'auto',
        padding: '24px 32px',
      }}>
        {ActiveComponent && <ActiveComponent />}
      </div>
    </div>
  );
}
