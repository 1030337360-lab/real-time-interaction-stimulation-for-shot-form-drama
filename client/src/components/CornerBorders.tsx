import React, { useEffect, useState } from 'react';

interface CornerBordersProps {
  isActive: boolean;
}

export const CornerBorders = React.memo<CornerBordersProps>(({ isActive }) => {
  const [shrinking, setShrinking] = useState(false);

  useEffect(() => {
    if (isActive) {
      setShrinking(true);
    } else {
      setShrinking(false);
    }
  }, [isActive]);

  if (!isActive) return null;

  return (
    <div className="corner-borders">
      <div className={`corner-border top-left ${shrinking ? 'shrinking' : ''}`} />
      <div className={`corner-border top-right ${shrinking ? 'shrinking' : ''}`} />
      <div className={`corner-border bottom-left ${shrinking ? 'shrinking' : ''}`} />
      <div className={`corner-border bottom-right ${shrinking ? 'shrinking' : ''}`} />
    </div>
  );
});

CornerBorders.displayName = 'CornerBorders';