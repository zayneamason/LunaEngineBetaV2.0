/**
 * Resolve hero frame URL from relative path or absolute URL.
 * Shared between LabPipeline, AudioTimeline, and MediaLibrary.
 */
export const heroUrl = (heroFrame, slug) => {
  if (!heroFrame) return heroFrame;
  if (heroFrame.startsWith('http')) return heroFrame;
  return slug ? `/kozmo/projects/${slug}/assets/${heroFrame}` : heroFrame;
};
