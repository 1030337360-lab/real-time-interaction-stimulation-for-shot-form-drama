import React, { useEffect, useState, useCallback, useRef } from 'react';
import { HighlightPhase } from '../hooks/useHighlightSync';
import { CornerBorders } from './CornerBorders';
import { HighlightAlert } from './HighlightAlert';
import { FlashEffect } from './FlashEffect';
import { ReactionPanel } from './ReactionPanel';
import { ComboOverlay } from './ComboOverlay';
import { ClickEffect } from './ClickEffect';
import { useParticleSystem } from '../hooks/useParticleSystem';

interface ClickEffectState {
  emoji: string;
  x: number;
  y: number;
}

interface ReactionOverlayProps {
  phase: HighlightPhase;
  timeToNext: number;
  highlights: number[];
  isMobile?: boolean;
  onReact?: (emoji: string) => void;
  onComboUpdate?: (count: number) => void;
}

export const ReactionOverlay = React.memo<ReactionOverlayProps>(({
  phase,
  timeToNext,
  highlights,
  isMobile = false,
  onReact,
  onComboUpdate,
}) => {
  const [showFlash, setShowFlash] = useState(false);
  const [showReactionPanel, setShowReactionPanel] = useState(false);
  const [comboCount, setComboCount] = useState(0);
  const [clickEffect, setClickEffect] = useState<ClickEffectState | null>(null);
  const consecutiveReactionsRef = useRef(0);
  const canvasElementRef = useRef<HTMLCanvasElement>(null);
  const { emit, emitBurst, destroy } = useParticleSystem(canvasElementRef);

  useEffect(() => {
    let flashTimer: ReturnType<typeof setTimeout> | null = null;
    let panelTimer: ReturnType<typeof setTimeout> | null = null;
    let hideTimer: ReturnType<typeof setTimeout> | null = null;

    switch (phase) {
      case 'warning':
        break;
      case 'alert':
        break;
      case 'active':
        setShowFlash(true);
        flashTimer = setTimeout(() => setShowFlash(false), 300);
        break;
      case 'cooldown':
        panelTimer = setTimeout(() => {
          setShowReactionPanel(true);
        }, 500);
        hideTimer = setTimeout(() => {
          setShowReactionPanel(false);
        }, 4500);
        break;
      case 'idle':
        setShowReactionPanel(false);
        break;
    }

    return () => {
      if (flashTimer) clearTimeout(flashTimer);
      if (panelTimer) clearTimeout(panelTimer);
      if (hideTimer) clearTimeout(hideTimer);
    };
  }, [phase]);

  useEffect(() => {
    return () => {
      destroy();
    };
  }, [destroy]);

  const handleReact = useCallback(
    (emoji: string, clickX: number, clickY: number) => {
      consecutiveReactionsRef.current += 1;
      const newComboCount = consecutiveReactionsRef.current;
      setComboCount(newComboCount);
      onComboUpdate?.(newComboCount);

      setClickEffect({ emoji, x: clickX, y: clickY });

      if (newComboCount >= 3) {
        emitBurst(window.innerWidth / 2, window.innerHeight / 2, emoji);
      } else {
        emit(clickX, clickY, emoji, isMobile ? 4 : 8);
      }

      onReact?.(emoji);
    },
    [emit, emitBurst, onReact, onComboUpdate, isMobile]
  );

  const handleClickEffectComplete = useCallback(() => {
    setClickEffect(null);
  }, []);

  useEffect(() => {
    if (phase !== 'idle' && phase !== 'cooldown') {
      consecutiveReactionsRef.current = 0;
    }
  }, [phase]);

  if (highlights.length === 0) return null;

  return (
    <div className="reaction-overlay">
      {phase === 'warning' && !isMobile && <CornerBorders isActive={true} />}

      {phase === 'alert' && !isMobile && (
        <HighlightAlert secondsLeft={Math.max(0, timeToNext)} />
      )}

      {showFlash && <FlashEffect />}

      {showFlash && <div className="overlay-shake" />}

      {showReactionPanel && (
        <ReactionPanel
          onReact={handleReact}
          onClose={() => setShowReactionPanel(false)}
          isMobile={isMobile}
        />
      )}

      {clickEffect && (
        <ClickEffect
          emoji={clickEffect.emoji}
          x={clickEffect.x}
          y={clickEffect.y}
          onComplete={handleClickEffectComplete}
        />
      )}

      <ComboOverlay comboCount={comboCount} />

      <canvas
        ref={canvasElementRef}
        className="particle-canvas"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 10,
        }}
      />
    </div>
  );
});

ReactionOverlay.displayName = 'ReactionOverlay';