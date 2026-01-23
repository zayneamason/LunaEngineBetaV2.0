import React from 'react';

const GradientOrb = ({ className = '', color1, color2, delay = 0 }) => (
  <div
    className={`absolute rounded-full blur-3xl opacity-20 animate-pulse-slow pointer-events-none ${className}`}
    style={{
      background: `radial-gradient(circle, ${color1} 0%, ${color2} 50%, transparent 70%)`,
      animationDelay: `${delay}s`,
    }}
  />
);

export default GradientOrb;
