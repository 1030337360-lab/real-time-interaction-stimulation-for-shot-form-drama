import { useState, useEffect, useRef, useMemo, useCallback } from 'react';

export type HighlightPhase =
  | 'idle'
  | 'warning'
  | 'alert'
  | 'active'
  | 'cooldown';

export interface HighlightState {
  phase: HighlightPhase;
  nearestHighlight: number | null;
  timeToNext: number;
}

interface UseHighlightSyncOptions {
  enabled?: boolean;
}

export function useHighlightSync(
  highlights: number[],
  currentTime: number,
  duration: number,
  isPaused: boolean,
  options: UseHighlightSyncOptions = {}
): HighlightState {
  const { enabled = true } = options;

  const [state, setState] = useState<HighlightState>({
    phase: 'idle',
    nearestHighlight: null,
    timeToNext: Infinity,
  });

  const stateRef = useRef<HighlightState>({
    phase: 'idle',
    nearestHighlight: null,
    timeToNext: Infinity,
  });

  const cooldownStartRef = useRef<number | null>(null);
  const activeStartRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number>(currentTime);

  const upcomingHighlights = useMemo(() => {
    if (!enabled || highlights.length === 0 || duration <= 0) {
      return [];
    }
    return highlights
      .map((p) => (p / 100) * duration)
      .filter((t) => t > currentTime)
      .sort((a, b) => a - b);
  }, [highlights, currentTime, duration, enabled]);

  const nearest = upcomingHighlights[0] ?? null;

  useEffect(() => {
    if (!enabled) {
      const idleState: HighlightState = {
        phase: 'idle',
        nearestHighlight: null,
        timeToNext: Infinity,
      };
      setState(idleState);
      stateRef.current = idleState;
      return;
    }

    if (!nearest || highlights.length === 0) {
      const newState: HighlightState = {
        phase: 'idle',
        nearestHighlight: null,
        timeToNext: Infinity,
      };

      if (stateRef.current.phase !== 'idle') {
        setState(newState);
        stateRef.current = newState;
      }
      return;
    }

    const timeToNext = nearest - currentTime;
    const now = Date.now();

    if (isPaused) {
      return;
    }

    const deltaTime = currentTime - lastTimeRef.current;
    lastTimeRef.current = currentTime;

    let newPhase: HighlightPhase = stateRef.current.phase;

    if (newPhase !== 'cooldown' && newPhase !== 'active') {
      if (Math.abs(deltaTime) > 2) {
        newPhase = 'idle';
      }
    }

    if (newPhase === 'cooldown') {
      const secondsInCooldown = (now - (cooldownStartRef.current || now)) / 1000;
      if (secondsInCooldown >= 4) {
        newPhase = 'idle';
        cooldownStartRef.current = null;
      }
    } else if (newPhase === 'active') {
      const secondsInActive = (now - (activeStartRef.current || now)) / 1000;
      if (secondsInActive >= 0.5) {
        newPhase = 'cooldown';
        cooldownStartRef.current = now;
        activeStartRef.current = null;
      }
    } else {
      if (timeToNext <= 0) {
        newPhase = 'active';
        activeStartRef.current = now;
      } else if (timeToNext < 3) {
        newPhase = 'alert';
      } else if (timeToNext < 5) {
        newPhase = 'warning';
      } else {
        newPhase = 'idle';
      }
    }

    if (newPhase !== stateRef.current.phase) {
      if (typeof window !== 'undefined' && (window as any).__highlightDebug !== false) {
        console.log('[useHighlightSync] %s → %s (timeToNext=%.1fs, nearest=%s%%)',
          stateRef.current.phase, newPhase, timeToNext,
          nearest ? ((nearest / duration) * 100).toFixed(1) : 'null');
      }
      const newState: HighlightState = {
        phase: newPhase,
        nearestHighlight: nearest,
        timeToNext: timeToNext,
      };

      console.log('HighlightSync state change:', {
        from: stateRef.current.phase,
        to: newPhase,
        timeToNext,
        nearest,
        currentTime,
        highlightsCount: highlights.length,
        isPaused,
      });

      setState(newState);
      stateRef.current = newState;
    } else if (Math.abs(timeToNext - stateRef.current.timeToNext) > 0.1) {
      stateRef.current.timeToNext = timeToNext;
    }
  }, [currentTime, isPaused, highlights, duration, nearest, enabled, upcomingHighlights]);

  const reset = useCallback(() => {
    const idleState: HighlightState = {
      phase: 'idle',
      nearestHighlight: null,
      timeToNext: Infinity,
    };
    setState(idleState);
    stateRef.current = idleState;
    cooldownStartRef.current = null;
    activeStartRef.current = null;
    lastTimeRef.current = 0;
  }, []);

  useEffect(() => {
    return () => {
      reset();
    };
  }, [reset]);

  return state;
}