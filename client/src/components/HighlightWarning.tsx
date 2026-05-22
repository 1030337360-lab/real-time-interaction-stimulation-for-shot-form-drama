import React, { useMemo } from 'react';

interface HighlightWarningProps {
  highlights: number[];
  currentTime: number;
  duration: number;
}

export const HighlightWarning = React.memo<HighlightWarningProps>(({
  highlights,
  currentTime,
  duration,
}) => {
  const upcomingHighlights = useMemo(() => {
    if (highlights.length === 0 || duration <= 0) return [];

    return highlights
      .map((point) => {
        const timePercent = (point / 100) * duration;
        return {
          point,
          timePercent,
          timeToHighlight: timePercent - currentTime,
        };
      })
      .filter((h) => h.timeToHighlight > 0)
      .sort((a, b) => a.timePercent - b.timePercent);
  }, [highlights, currentTime, duration]);

  if (upcomingHighlights.length === 0) return null;

  const nearestHighlight = upcomingHighlights[0];
  const showSweep = nearestHighlight && nearestHighlight.timeToHighlight <= 3 && nearestHighlight.timeToHighlight > 0;

  return (
    <>
      {upcomingHighlights.map((highlight, index) => (
        <React.Fragment key={highlight.point}>
          <div
            className={`highlight-marker warning ${index === 0 && showSweep ? 'active' : ''}`}
            style={{ left: `${highlight.point}%` }}
          />
        </React.Fragment>
      ))}

      {showSweep && (
        <div
          className="highlight-sweep"
          style={{
            left: `${nearestHighlight.point}%`,
            animationDuration: `${Math.min(0.5, nearestHighlight.timeToHighlight)}s`,
          }}
        />
      )}
    </>
  );
});

HighlightWarning.displayName = 'HighlightWarning';