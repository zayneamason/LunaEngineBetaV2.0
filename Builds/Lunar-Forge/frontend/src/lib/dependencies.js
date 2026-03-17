/**
 * Static dependency map for Luna Engine components.
 * Hand-authored — update when new pages/widgets/collections are added.
 */
export const DEPENDENCIES = {
  pages: {
    observatory: {
      requires: [],
      enables_widgets: ["qa", "debug", "vk", "cache"],
      description: "Diagnostic UI for memory matrix and QA system",
    },
    eclissi: {
      requires: [],
      enables_widgets: ["engine", "voice", "memory", "thought", "prompt"],
      description: "Main chat interface with Luna",
    },
    kozmo: {
      requires: [],
      enables_widgets: [],
      description: "Creative studio companion for writing projects",
    },
    guardian: {
      requires: ["kinoni_knowledge"],
      enables_widgets: [],
      description: "Community knowledge governance dashboard",
    },
    settings: {
      requires: [],
      enables_widgets: [],
      description: "Configuration panel for LLM, identity, voice, personality",
    },
    studio: {
      requires: [],
      enables_widgets: ["lunascript"],
      description: "Lunar Studio diagnostic frontend",
    },
  },

  collections: {
    luna_system: {
      required_by: ["eclissi"],
      critical: true,
      description: "Luna's self-knowledge: help docs, feature guides, navigation",
    },
    kinoni_knowledge: {
      required_by: ["guardian"],
      critical: false,
      description: "Kinoni community cultural knowledge base (883 chunks)",
    },
    dataroom: {
      required_by: [],
      critical: false,
      description: "Investor-facing documents for Project Eclipse",
    },
  },

  widgets: {
    engine:     { needs_page: "eclissi",     description: "Engine status and session info" },
    voice:      { needs_page: "eclissi",     description: "Voice input/output controls" },
    memory:     { needs_page: "eclissi",     description: "Memory matrix inspection" },
    qa:         { needs_page: "observatory", description: "QA assertion testing panel" },
    prompt:     { needs_page: "eclissi",     description: "Prompt preview and debugging" },
    debug:      { needs_page: "observatory", description: "Pipeline diagnostic tools" },
    vk:         { needs_page: "observatory", description: "Voight-Kampff personality tests" },
    cache:      { needs_page: "observatory", description: "Response cache inspection" },
    thought:    { needs_page: "eclissi",     description: "Luna's thought process display" },
    lunascript: { needs_page: "studio",      description: "Cognitive signature analysis" },
  },
};
