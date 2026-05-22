import React, { useEffect, useState, useCallback } from 'react';

interface ReactionPanelProps {
  onReact: (emoji: string, clickX: number, clickY: number) => void;
  onClose: () => void;
  isMobile?: boolean;
}

export const ReactionPanel = React.memo<ReactionPanelProps>(({
  onReact,
  onClose,
  isMobile = false,
}) => {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const hideTimer = setTimeout(() => {
      setVisible(false);
      setTimeout(onClose, 300);
    }, 4000);

    return () => clearTimeout(hideTimer);
  }, [onClose]);

  const emojis = isMobile ? ['🔥', '❤️'] : ['🔥', '❤️', '👏', '😱'];

  const handleClick = useCallback(
    (emoji: string, e: React.MouseEvent) => {
      e.stopPropagation();
      const rect = e.currentTarget.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      onReact(emoji, x, y);
      setVisible(false);
      setTimeout(onClose, 300);
    },
    [onReact, onClose]
  );

  if (!visible) return null;

  return (
    <div className="reaction-panel" onClick={(e) => e.stopPropagation()}>
      {emojis.map((emoji, index) => (
        <button
          key={emoji}
          className="reaction-btn"
          style={{ animationDelay: `${index * 0.1}s` }}
          onClick={(e) => handleClick(emoji, e)}
        >
          {emoji}
        </button>
      ))}
    </div>
  );
});

ReactionPanel.displayName = 'ReactionPanel';