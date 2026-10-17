import { useState, useEffect, useRef } from 'react';

/**
 * Hook to detect whether the user has enabled the prefers-reduced-motion media query.
 */
export function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

    const handleChange = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
    } else {
      // Legacy Safari fallback
      mediaQuery.addListener(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handleChange);
      } else {
        mediaQuery.removeListener(handleChange);
      }
    };
  }, []);

  return prefersReducedMotion;
}

/**
 * Hook to track tab visibility (document.visibilityState).
 * Returns true when tab is active/visible, false when hidden in background.
 */
export function usePageVisibility(): boolean {
  const [isVisible, setIsVisible] = useState<boolean>(() => {
    if (typeof document === 'undefined') return true;
    return !document.hidden;
  });

  useEffect(() => {
    if (typeof document === 'undefined') return;

    const syncVisibility = () => {
      const hidden = document.hidden;
      setIsVisible(!hidden);
      if (hidden) {
        document.documentElement.classList.add('tab-hidden');
      } else {
        document.documentElement.classList.remove('tab-hidden');
      }
    };

    // Initial check
    syncVisibility();

    document.addEventListener('visibilitychange', syncVisibility);
    return () => {
      document.removeEventListener('visibilitychange', syncVisibility);
    };
  }, []);

  return isVisible;
}

/**
 * Hook for smooth count-up animations on numerals.
 * - Respects prefers-reduced-motion (resolves immediately to target).
 * - Pauses progress while the browser tab is hidden and resumes when visible.
 * - Animates via requestAnimationFrame with exponential ease-out curve.
 */
export function useCountUp(
  target: number,
  options: {
    duration?: number;
    enabled?: boolean;
    startValue?: number;
  } = {}
): number {
  const { duration = 800, enabled = true, startValue = 0 } = options;
  const prefersReduced = usePrefersReducedMotion();
  const isVisible = usePageVisibility();

  const [currentValue, setCurrentValue] = useState<number>(() => {
    if (!enabled || prefersReduced) return target;
    return startValue;
  });

  const progressRef = useRef<number>(enabled && !prefersReduced ? 0 : 1);
  const startTimeRef = useRef<number | null>(null);
  const elapsedBeforePauseRef = useRef<number>(0);
  const animationFrameRef = useRef<number | null>(null);

  const previousTargetRef = useRef<number>(target);

  useEffect(() => {
    if (previousTargetRef.current !== target) {
      previousTargetRef.current = target;
      progressRef.current = 0;
      elapsedBeforePauseRef.current = 0;
      startTimeRef.current = null;
    }

    if (!enabled || prefersReduced) {
      setCurrentValue(target);
      progressRef.current = 1;
      return;
    }

    if (!isVisible) {
      // Tab became hidden: pause animation
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      startTimeRef.current = null;
      return;
    }

    // If already completed target, finish
    if (progressRef.current >= 1) {
      return;
    }

    const step = (now: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = now;
      }

      const elapsed = elapsedBeforePauseRef.current + (now - startTimeRef.current);
      const p = Math.min(1, elapsed / duration);
      progressRef.current = p;

      // Ease-out expo curve: 1 - 2^(-10 * progress)
      const ease = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
      const val = startValue + (target - startValue) * ease;
      setCurrentValue(val);

      if (p < 1) {
        animationFrameRef.current = requestAnimationFrame(step);
      } else {
        elapsedBeforePauseRef.current = duration;
        animationFrameRef.current = null;
      }
    };

    animationFrameRef.current = requestAnimationFrame(step);

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [target, duration, enabled, prefersReduced, isVisible, startValue]);

  return currentValue;
}

/**
 * Hook for smooth gauge and chart sweep / draw-in animations (0 -> 1 progress).
 * - Animates from 0 to 1 over `duration` ms.
 * - Immediately returns 1 if prefers-reduced-motion is active.
 * - Pauses when tab is hidden and resumes when visible.
 */
export function useMotionProgress(
  options: {
    duration?: number;
    enabled?: boolean;
    delay?: number;
  } = {}
): number {
  const { duration = 750, enabled = true, delay = 0 } = options;
  const prefersReduced = usePrefersReducedMotion();
  const isVisible = usePageVisibility();

  const [progress, setProgress] = useState<number>(() => {
    if (!enabled || prefersReduced) return 1;
    return 0;
  });

  const startTimeRef = useRef<number | null>(null);
  const elapsedBeforePauseRef = useRef<number>(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled || prefersReduced) {
      setProgress(1);
      return;
    }

    if (!isVisible) {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
      startTimeRef.current = null;
      return;
    }

    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const startAnimation = () => {
      const step = (now: number) => {
        if (startTimeRef.current === null) {
          startTimeRef.current = now;
        }

        const elapsed = elapsedBeforePauseRef.current + (now - startTimeRef.current);
        const p = Math.min(1, elapsed / duration);

        // Ease-out cubic: 1 - (1 - p)^3
        const ease = 1 - Math.pow(1 - p, 3);
        setProgress(ease);

        if (p < 1) {
          frameRef.current = requestAnimationFrame(step);
        } else {
          elapsedBeforePauseRef.current = duration;
          frameRef.current = null;
        }
      };

      frameRef.current = requestAnimationFrame(step);
    };

    if (delay > 0 && elapsedBeforePauseRef.current === 0) {
      timeoutId = setTimeout(startAnimation, delay);
    } else {
      startAnimation();
    }

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [duration, enabled, prefersReduced, isVisible, delay]);

  return progress;
}
