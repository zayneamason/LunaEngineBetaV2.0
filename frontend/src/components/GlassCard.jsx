import React from 'react';

const GlassCard = ({
  children,
  className = '',
  onClick,
  hover = true,
  dashed = false,
  padding = 'p-4'
}) => {
  const baseClasses = 'backdrop-blur-xl bg-white/5 rounded-2xl transition-all duration-300';
  const borderClasses = dashed
    ? 'border border-dashed border-white/20'
    : 'border border-white/10';
  const hoverClasses = onClick && hover
    ? 'cursor-pointer hover:bg-white/[0.08] hover:border-white/20'
    : '';

  return (
    <div
      onClick={onClick}
      className={`${baseClasses} ${borderClasses} ${hoverClasses} ${padding} ${className}`}
    >
      {children}
    </div>
  );
};

export default GlassCard;
