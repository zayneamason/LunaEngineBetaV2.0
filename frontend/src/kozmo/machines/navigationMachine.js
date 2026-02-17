/**
 * KOZMO Navigation State Machine
 *
 * Manages navigation between KOZMO's three modes (SCRIBO, CODEX, LAB) with:
 * - State preservation across mode switches
 * - Unsaved changes warnings
 * - Previous mode tracking for back navigation
 * - localStorage persistence
 *
 * See: /Users/zayneamason/.claude/plans/dreamy-bubbling-trinket.md
 */

import { setup, assign } from 'xstate';

export const navigationMachine = setup({
  guards: {
    allowNavigation: ({ context }) => {
      // If no unsaved changes, allow navigation
      if (!context.isDirty) return true;

      // If there are unsaved changes, ask for confirmation
      return window.confirm('You have unsaved changes. Discard and switch modes?');
    },
  },
}).createMachine({
  id: 'kozmo-navigation',
  initial: 'codex', // Default mode on first load
  context: {
    // State preservation containers - hold component-level state across mode switches
    scriboState: {
      selectedScene: null,
      expandedNodes: [],
      searchQuery: '',
      searchResults: null,
      rightPanel: 'chat',
    },
    codexState: {
      searchQuery: '',
      showCreateForm: false,
      rightPanel: 'agents',
      selectedEntitySlug: null,  // Set when navigating from SCRIBO entity click
      selectedEntityType: null,   // Set when navigating from SCRIBO entity click
    },
    labState: {
      selectedShot: 'sh001',
      shots: [],
      rightPanel: 'camera',
      generatedPrompt: '',
      timelineHeight: 220,
    },
    previousMode: null, // Tracks last mode for "back" navigation
    isDirty: false,     // Tracks unsaved changes in current mode
  },
  states: {
    scribo: {
      entry: assign({
        previousMode: ({ context, event }) => {
          // Only update previousMode if we're transitioning FROM another mode
          if (event && event.type && event.type.startsWith('TO_')) {
            const fromMode = event.type === 'TO_SCRIBO'
              ? (context.previousMode || 'codex')
              : context.previousMode;
            return fromMode;
          }
          return context.previousMode;
        },
      }),
      on: {
        TO_CODEX: {
          target: 'codex',
          guard: 'allowNavigation',
          actions: assign({
            previousMode: () => 'scribo',
            // Capture entity selection from navigation event
            codexState: ({ context, event }) => ({
              ...context.codexState,
              selectedEntitySlug: event?.entitySlug || null,
              selectedEntityType: event?.entityType || null,
            }),
          }),
        },
        TO_LAB: {
          target: 'lab',
          guard: 'allowNavigation',
          actions: assign({
            previousMode: () => 'scribo',
          }),
        },
        SAVE_SCRIBO_STATE: {
          actions: assign({
            scriboState: ({ context, event }) => ({
              ...context.scriboState,
              ...(event?.state || {}),
            }),
          }),
        },
        SET_DIRTY: {
          actions: assign({
            isDirty: ({ event }) => event.value,
          }),
        },
      },
    },
    codex: {
      entry: assign({
        previousMode: ({ context, event }) => {
          if (event && event.type && event.type.startsWith('TO_')) {
            const fromMode = event.type === 'TO_CODEX'
              ? (context.previousMode || 'scribo')
              : context.previousMode;
            return fromMode;
          }
          return context.previousMode;
        },
      }),
      on: {
        TO_SCRIBO: {
          target: 'scribo',
          actions: assign({
            previousMode: () => 'codex',
          }),
        },
        TO_LAB: {
          target: 'lab',
          actions: assign({
            previousMode: () => 'codex',
          }),
        },
        SAVE_CODEX_STATE: {
          actions: assign({
            codexState: ({ context, event }) => ({
              ...context.codexState,
              ...(event?.state || {}),
            }),
          }),
        },
      },
    },
    lab: {
      entry: assign({
        previousMode: ({ context, event }) => {
          if (event && event.type && event.type.startsWith('TO_')) {
            const fromMode = event.type === 'TO_LAB'
              ? (context.previousMode || 'codex')
              : context.previousMode;
            return fromMode;
          }
          return context.previousMode;
        },
      }),
      on: {
        TO_SCRIBO: {
          target: 'scribo',
          actions: assign({
            previousMode: () => 'lab',
            // Allow LAB→SCRIBO navigation to carry scribo state (e.g. selectedScene)
            scriboState: ({ context, event }) => ({
              ...context.scriboState,
              ...(event?.scriboState || {}),
            }),
          }),
        },
        SAVE_SCRIBO_STATE: {
          actions: assign({
            scriboState: ({ context, event }) => ({
              ...context.scriboState,
              ...(event?.state || {}),
            }),
          }),
        },
        TO_CODEX: {
          target: 'codex',
          actions: assign({
            previousMode: () => 'lab',
          }),
        },
        SAVE_LAB_STATE: {
          actions: assign({
            labState: ({ context, event }) => ({
              ...context.labState,
              ...(event?.state || {}),
            }),
          }),
        },
      },
    },
  },
});
