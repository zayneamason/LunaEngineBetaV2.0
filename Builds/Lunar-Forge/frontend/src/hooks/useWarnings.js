import { useMemo } from "react";
import { DEPENDENCIES } from "../lib/dependencies";

/**
 * Returns an array of { id, severity, message, section, fixKey? } warnings
 * based on the current build configuration state.
 */
export function useWarnings({ pages, widgets, collections, patches, chain, remap, secretsMode }) {
  return useMemo(() => {
    const warnings = [];

    // ERROR: luna_system collection disabled
    if (collections.luna_system === false) {
      warnings.push({
        id: "coll-luna-system",
        severity: "error",
        message: "Luna cannot function without self-knowledge. Enable luna_system.",
        section: "collections",
        fixKey: { type: "collection", name: "luna_system", value: true },
      });
    }

    // ERROR: No bootstrap patches selected
    if (!patches || patches.length === 0) {
      warnings.push({
        id: "patches-empty",
        severity: "error",
        message: "Luna will boot with no personality. Select at least sovereignty + honesty.",
        section: "patches",
      });
    }

    // WARN: Widget enabled but its parent page is disabled
    for (const [widgetName, widgetDef] of Object.entries(DEPENDENCIES.widgets)) {
      if (widgets[widgetName] && pages[widgetDef.needs_page] === false) {
        warnings.push({
          id: `orphan-widget-${widgetName}`,
          severity: "warn",
          message: `${widgetName} widget is enabled but ${widgetDef.needs_page} page is disabled. ${widgetName} has nowhere to render.`,
          section: "widgets",
          fixKey: { type: "widget", name: widgetName, value: false },
        });
      }
    }

    // WARN: Guardian page on without kinoni_knowledge
    if (pages.guardian && !collections.kinoni_knowledge) {
      warnings.push({
        id: "guardian-no-kinoni",
        severity: "warn",
        message: "Guardian page is enabled but kinoni_knowledge collection is missing. Guardian will have no data.",
        section: "pages",
        fixKey: { type: "collection", name: "kinoni_knowledge", value: true },
      });
    }

    // WARN: Secrets mode is template and no env keys configured
    if (secretsMode === "template" || !secretsMode) {
      warnings.push({
        id: "secrets-template",
        severity: "warn",
        message: "No API keys will be configured. User will need to enter keys on first launch via Settings.",
        section: "secrets",
      });
    }

    // INFO: Remap active
    if (remap?.nexus) {
      warnings.push({
        id: "remap-active",
        severity: "info",
        message: `Nexus tab will show as "${remap.nexus.to}" in the header instead of "Studio".`,
        section: "remap",
      });
    }

    // INFO: Settings page disabled
    if (pages.settings === false) {
      warnings.push({
        id: "settings-disabled",
        severity: "info",
        message: "Users won't be able to change LLM providers or personality after install.",
        section: "pages",
      });
    }

    return warnings;
  }, [pages, widgets, collections, patches, chain, remap, secretsMode]);
}
