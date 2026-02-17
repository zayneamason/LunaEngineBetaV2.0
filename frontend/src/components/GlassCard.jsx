import React from 'react';

const GlassCard = ({
  children,
  className = '',
  onClick,
  hover = true,
  dashed = false,
  padding = 'p-4',
  glow = false,
}) => {
  return (
    <div
      onClick={onClick}
      className={`rounded transition-all duration-300 ${padding} ${className}`}
      style={{
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        background: 'rgba(18, 18, 26, 0.45)',
        border: dashed
          ? '1px dashed rgba(30, 30, 46, 0.8)'
          : '1px solid rgba(30, 30, 46, 0.5)',
        boxShadow: glow
          ? '0 0 0 1px rgba(192, 132, 252, 0.08), 0 4px 30px rgba(0, 0, 0, 0.5), 0 0 40px rgba(192, 132, 252, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.04)'
          : '0 0 0 1px rgba(30, 30, 46, 0.2), 0 4px 30px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.04)',
        ...(onClick && hover ? { cursor: 'pointer' } : {}),
      }}
      onMouseEnter={onClick && hover ? (e) => {
        e.currentTarget.style.background = 'rgba(18, 18, 26, 0.6)';
        e.currentTarget.style.borderColor = 'rgba(30, 30, 46, 0.8)';
      } : undefined}
      onMouseLeave={onClick && hover ? (e) => {
        e.currentTarget.style.background = 'rgba(18, 18, 26, 0.45)';
        e.currentTarget.style.borderColor = 'rgba(30, 30, 46, 0.5)';
      } : undefined}
    >
      {children}
    </div>
  );
};

export default GlassCard;
