import { useState, useRef, useCallback, useMemo, useLayoutEffect, useEffect } from 'react';

const CHUNK = 30;
const MAX_RENDERED = 60;

/**
 * useWindowedMessages — Guardian-style windowed message rendering.
 *
 * Shows last CHUNK messages initially. Lazy-loads older messages on scroll-up.
 * Trims DOM when exceeding MAX_RENDERED. Preserves scroll position on prepend.
 */
export function useWindowedMessages(allMessages) {
  const [windowStart, setWindowStart] = useState(() =>
    Math.max(0, allMessages.length - CHUNK)
  );
  const [windowEnd, setWindowEnd] = useState(allMessages.length);

  const scrollRef = useRef(null);
  const isAtBottomRef = useRef(true);
  const loadingRef = useRef(false);
  const prevScrollHeightRef = useRef(null);
  const didPrependRef = useRef(false);

  // When new messages arrive and user is at the bottom, extend the window
  useEffect(() => {
    if (isAtBottomRef.current) {
      const newEnd = allMessages.length;
      const newStart = Math.max(0, newEnd - Math.min(MAX_RENDERED, newEnd));
      setWindowEnd(newEnd);
      setWindowStart(newStart);
    } else {
      // User is scrolled up — just update the end boundary so they can scroll down
      setWindowEnd(allMessages.length);
    }
  }, [allMessages.length]);

  // Preserve scroll position after prepending older messages
  useLayoutEffect(() => {
    if (didPrependRef.current && scrollRef.current && prevScrollHeightRef.current != null) {
      const el = scrollRef.current;
      const delta = el.scrollHeight - prevScrollHeightRef.current;
      el.scrollTop += delta;
      prevScrollHeightRef.current = null;
      didPrependRef.current = false;
      setTimeout(() => { loadingRef.current = false; }, 100);
    }
  });

  const loadOlder = useCallback(() => {
    if (loadingRef.current || windowStart === 0) return;
    loadingRef.current = true;

    const el = scrollRef.current;
    if (el) prevScrollHeightRef.current = el.scrollHeight;
    didPrependRef.current = true;

    const newStart = Math.max(0, windowStart - CHUNK);
    let newEnd = windowEnd;

    if (newEnd - newStart > MAX_RENDERED) {
      newEnd = newStart + MAX_RENDERED;
    }

    setWindowStart(newStart);
    setWindowEnd(newEnd);
  }, [windowStart, windowEnd]);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;

    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    isAtBottomRef.current = distFromBottom < 50;

    if (!loadingRef.current && el.scrollTop < 100 && windowStart > 0) {
      loadOlder();
    }
  }, [windowStart, loadOlder]);

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    const newEnd = allMessages.length;
    const newStart = Math.max(0, newEnd - CHUNK);
    setWindowEnd(newEnd);
    setWindowStart(newStart);
    isAtBottomRef.current = true;

    requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTo({ top: el.scrollHeight, behavior });
    });
  }, [allMessages.length]);

  const visibleMessages = useMemo(
    () => allMessages.slice(windowStart, windowEnd),
    [allMessages, windowStart, windowEnd]
  );

  const canLoadOlder = windowStart > 0;

  return {
    visibleMessages,
    onScroll,
    scrollRef,
    canLoadOlder,
    scrollToBottom,
    isAtBottom: isAtBottomRef,
  };
}
