import React, { useMemo } from 'react';

interface HighlightAlertProps {
  secondsLeft: number;
}

export const HighlightAlert = React.memo<HighlightAlertProps>(({ secondsLeft }) => {
  const circumference = 2 * Math.PI * 45;
  const strokeDasharray = useMemo(() => {
    const progress = secondsLeft / 3;
    const dashLength = progress * circumference;
    return `${dashLength} ${circumference}`;
  }, [secondsLeft, circumference]);

  return (
    <div className="highlight-alert-container">
      <div className="countdown-ring">
        <svg viewBox="0 0 100 100">
          <circle
            className="countdown-bg"
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="rgba(255, 215, 0, 0.2)"
            strokeWidth="4"
          />
          <circle
            className="countdown-progress"
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="url(#countdownGradient)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={strokeDasharray}
            transform="rotate(-90 50 50)"
          />
          <defs>
            <linearGradient id="countdownGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#ffd700" />
              <stop offset="100%" stopColor="#ff8c00" />
            </linearGradient>
          </defs>
        </svg>
        <span className="countdown-number">{Math.ceil(secondsLeft)}</span>
      </div>
      <div className="alert-text">高能预警</div>
    </div>
  );
});

HighlightAlert.displayName = 'HighlightAlert';