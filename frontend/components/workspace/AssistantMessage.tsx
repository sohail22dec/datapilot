import React from "react";
import { DataPilotIcon } from "../brand/DataPilotLogo";

interface AssistantMessageProps {
  content: string;
  timestamp: string;
}

export const AssistantMessage: React.FC<AssistantMessageProps> = ({
  content,
  timestamp,
}) => {
  // Helper to format text with bold markers or numbers cleanly
  const renderFormattedContent = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={index} className="font-semibold text-white">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="flex items-start justify-start gap-3 my-3.5 w-full">
      {/* Brand Icon Avatar */}
      <div className="shrink-0 mt-0.5">
        <DataPilotIcon size="md" />
      </div>

      {/* Softer Dark Response Card */}
      <div className="bg-[#242834] border border-[#323849] rounded-2xl rounded-tl-xs px-5 py-3.5 max-w-[660px] shadow-sm flex flex-col gap-2">
        <div className="text-[14.5px] text-[#F1F5F9] leading-relaxed select-text whitespace-pre-wrap">
          {renderFormattedContent(content)}
        </div>
        <span className="text-[11px] text-[#94A3B8] font-normal">
          {timestamp}
        </span>
      </div>
    </div>
  );
};
