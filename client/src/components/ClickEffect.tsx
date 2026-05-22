import React, { useEffect, useState } from 'react';

interface ClickEffectProps {
  emoji: string;
  x: number;
  y: number;
  onComplete: () => void;
}

export const ClickEffect = React.memo<ClickEffectProps>(({ emoji, x, y, onComplete }) => {
  const [showText, setShowText] = useState(false);

  useEffect(() => {
    const textTimer = setTimeout(() => setShowText(true), 200);
    const completeTimer = setTimeout(() => onComplete(), 1500);
    return () => {
      clearTimeout(textTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  return (
    <div className="click-effect-container" style={{ left: x, top: y }}>
      <div className="clicked-emoji">{emoji}</div>
      {showText && (
        <div className="click-effect-text">+精彩!</div>
      )}
    </div>
  );
});

ClickEffect.displayName = 'ClickEffect';