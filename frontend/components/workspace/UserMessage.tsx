import React from "react";
import { UserAvatar } from "../common/UserAvatar";

interface UserMessageProps {
  content: string;
  timestamp: string;
  userName?: string;
}

export const UserMessage: React.FC<UserMessageProps> = ({
  content,
  timestamp,
  userName = "Sohel Islam",
}) => {
  return (
    <div className="flex items-start justify-end gap-3 my-3.5 w-full">
      {/* Message bubble */}
      <div className="bg-[#FEC50B] text-[#09090B] rounded-2xl rounded-tr-xs px-4.5 py-3 max-w-[500px] shadow-xs flex flex-col gap-1.5">
        <p className="text-[14.5px] leading-relaxed font-normal whitespace-pre-wrap select-text">
          {content}
        </p>
        <span className="text-[11px] text-[#09090B]/60 self-end font-medium">
          {timestamp}
        </span>
      </div>

      {/* Avatar on right */}
      <div className="shrink-0 mt-0.5">
        <UserAvatar name={userName} size="md" />
      </div>
    </div>
  );
};
