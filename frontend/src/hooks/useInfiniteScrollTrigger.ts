import { useEffect, useRef } from "react";

/** Fires `onIntersect` when the returned ref's element scrolls into view. The callback is read
 * from a ref so the observer is only ever created once, instead of being torn down and rebuilt
 * on every render just because the caller passed a fresh closure. */
export function useInfiniteScrollTrigger(onIntersect: () => void) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const callbackRef = useRef(onIntersect);
  callbackRef.current = onIntersect;

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) callbackRef.current();
      },
      { rootMargin: "400px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return sentinelRef;
}
