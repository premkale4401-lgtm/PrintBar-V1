import React from 'react';
import logoImg from '../assets/images/printbar_official_logo_1785588138896.jpg';

interface PrintBarLogoProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showText?: boolean;
  textColor?: string;
  useImage?: boolean;
}

export const PrintBarLogoIcon: React.FC<{ className?: string; size?: number }> = ({ className = 'w-7 h-7', size = 28 }) => {
  return (
    <div 
      className={`relative inline-flex items-center justify-center bg-blue-600 rounded-xl overflow-hidden shadow-xs shrink-0 select-none ${className}`}
      style={{ width: size, height: size }}
    >
      <svg 
        viewBox="0 0 100 100" 
        fill="none" 
        xmlns="http://www.w3.org/2000/svg"
        className="w-[82%] h-[82%]"
      >
        {/* White Printer Top Bar */}
        <path 
          d="M12 18 C12 14 15 11 19 11 L68 11 C82 11 90 20 90 34 C90 48 82 56 68 56 L55 56 L55 42 L68 42 C74 42 77 38 77 34 C77 29 74 25 68 25 L21 25 C16 25 12 21 12 18 Z" 
          fill="white" 
        />
        
        {/* Three Printer Control Dots on Top Bar */}
        <circle cx="21" cy="18" r="2.8" fill="#00aeef" />
        <circle cx="28" cy="18" r="2.8" fill="#ec008c" />
        <circle cx="35" cy="18" r="2.8" fill="#fff200" />

        {/* Black Slot Line inside Top Bar */}
        <rect x="18" y="29" width="50" height="4" rx="2" fill="#111827" />

        {/* Paper Sheet emerging from Slot with 4 CMYK Stripes */}
        <g clipPath="url(#paperClip)">
          {/* Cyan Stripe */}
          <rect x="23" y="35" width="8" height="52" fill="#00aeef" />
          {/* Magenta Stripe */}
          <rect x="31" y="35" width="8" height="52" fill="#ec008c" />
          {/* Yellow Stripe */}
          <rect x="39" y="35" width="8" height="52" fill="#fff200" />
          {/* Black/Dark Stripe */}
          <rect x="47" y="35" width="8" height="52" fill="#1e293b" />
        </g>

        {/* Paper Sheet Outline/Corner Radius Clip */}
        <defs>
          <clipPath id="paperClip">
            <rect x="23" y="35" width="32" height="52" rx="3" />
          </clipPath>
        </defs>
      </svg>
    </div>
  );
};

export const PrintBarLogo: React.FC<PrintBarLogoProps> = ({
  className = '',
  size = 'md',
  showText = true,
  textColor = 'text-slate-900',
  useImage = false
}) => {
  const sizePixels = {
    sm: 26,
    md: 34,
    lg: 42,
    xl: 52
  }[size];

  const textSizes = {
    sm: 'text-base',
    md: 'text-xl',
    lg: 'text-2xl',
    xl: 'text-3xl'
  }[size];

  return (
    <div className={`inline-flex items-center gap-2.5 ${className}`}>
      {useImage ? (
        <img 
          src={logoImg} 
          alt="PrintBar Logo" 
          className="rounded-xl shadow-xs object-cover border border-blue-500/30"
          style={{ width: sizePixels, height: sizePixels }}
        />
      ) : (
        <PrintBarLogoIcon size={sizePixels} />
      )}
      
      {showText && (
        <span className={`font-['Outfit'] font-bold tracking-tight ${textSizes} ${textColor}`}>
          PrintBar
        </span>
      )}
    </div>
  );
};
