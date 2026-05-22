import React, { useEffect, useState } from 'react';

interface FlashEffectProps {
  onComplete?: () => void;
}

export const FlashEffect = React.memo<FlashEffectProps>(({ onComplete }) => {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onComplete?.();
    }, 300);
    return () => clearTimeout(timer);
  }, [onComplete]);

  if (!visible) return null;

  return <div className="flash-effect" />;
});

FlashEffect.displayName = 'FlashEffect';