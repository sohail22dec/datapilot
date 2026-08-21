import React from "react";

interface DataPilotLogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  className?: string;
}

export const DataPilotIcon: React.FC<{ size?: "sm" | "md" | "lg"; className?: string }> = ({
  size = "md",
  className = "",
}) => {
  const sizeClasses = {
    sm: "w-8 h-8 rounded-lg",
    md: "w-10 h-10 rounded-xl",
    lg: "w-12 h-12 rounded-2xl",
  };

  const iconSizes = {
    sm: "w-4.5 h-4.5",
    md: "w-5.5 h-5.5",
    lg: "w-7 h-7",
  };

  return (
    <div
      className={`bg-gradient-to-b from-[#FFCF25] to-[#F5B800] flex items-center justify-center shadow-sm shrink-0 select-none ${sizeClasses[size]} ${className}`}
    >
      <svg
        viewBox="0 0 28 28"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`${iconSizes[size]} text-[#0E1117]`}
      >
        {/* Left Aerodynamic Wing Facet */}
        <path
          d="M14 3.5L4.5 21.5L13 17.2V3.5Z"
          fill="currentColor"
        />
        {/* Right Aerodynamic Wing Facet with Subtle Depth */}
        <path
          d="M14 3.5L23.5 21.5L15 17.2V3.5Z"
          fill="currentColor"
          opacity="0.82"
        />
        {/* Central Flight Vector Core Accent */}
        <circle cx="14" cy="11.5" r="1.2" fill="#FFCF25" />
      </svg>
    </div>
  );
};

export const DataPilotLogo: React.FC<DataPilotLogoProps> = ({
  size = "md",
  showText = true,
  className = "",
}) => {
  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      <DataPilotIcon size={size} />
      {showText && (
        <div className="flex items-center gap-1.5">
          <span className="text-[20px] font-bold tracking-tight text-white font-sans">
            DataPilot
          </span>
        </div>
      )}
    </div>
  );
};
