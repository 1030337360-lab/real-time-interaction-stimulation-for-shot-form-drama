import React, { useEffect, useState } from 'react';

interface ComboOverlayProps {
  comboCount: number;
  onComplete?: () => void;
}

export const ComboOverlay = React.memo<ComboOverlayProps>(({ comboCount, onComplete }) => {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (comboCount >= 3) {
      setVisible(true);
      const timer = setTimeout(() => {
        setVisible(false);
        onComplete?.();
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [comboCount, onComplete]);

  if (comboCount < 3 || !visible) return null;

  return (
    <div className="combo-overlay">
      <span className="combo-text">🔥 {comboCount} 连击！</span>
      <div className="combo-particles">
        {Array.from({ length: 20 }).map((_, i) => (
          <span
            key={i}
            className="combo-particle"
            style={{
              left: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 0.5}s`,
              backgroundColor: ['#ff4757', '#ffd700', '#ff6b81'][i % 3],
            }}
          />
        ))}
      </div>
    </div>
  );
});

ComboOverlay.displayName = 'ComboOverlay';