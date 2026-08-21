"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { Button } from "../ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";

interface ChatComposerProps {
  onSendMessage: (message: string) => void;
  isLoading?: boolean;
}

export const ChatComposer: React.FC<ChatComposerProps> = ({
  onSendMessage,
  isLoading = false,
}) => {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl + Enter or Cmd + Enter = New line (per user request)
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      setInput((prev) => prev + "\n");
      return;
    }

    // Normal Enter = Send
    if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  // Auto-grow textarea with compact max-height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        100
      )}px`;
    }
  }, [input]);

  return (
    <TooltipProvider>
      <div className="w-full max-w-4xl mx-auto px-4 md:px-8 mb-6">
        <div className="bg-[#242834] border border-[#323849] rounded-xl p-2 pl-4 flex items-end gap-2 shadow-sm focus-within:border-[#FEC50B]/70 focus-within:ring-1 focus-within:ring-[#FEC50B]/30 transition-all">
          {/* Compact Multiline Input */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your data..."
            rows={1}
            disabled={isLoading}
            className="flex-1 resize-none bg-transparent border-none py-1 text-[14px] text-[#F1F5F9] placeholder:text-[#94A3B8] focus:outline-none focus:ring-0 leading-relaxed max-h-24 overflow-y-auto"
          />

          {/* Compact Send button using shadcn Button & Tooltip */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="primary"
                size="iconSm"
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                aria-label="Send message"
                className={
                  !input.trim() || isLoading
                    ? "bg-[#333948] text-[#64748B] hover:bg-[#333948]"
                    : "bg-[#FEC50B] text-[#111827]"
                }
              >
                {isLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5 stroke-[2.4]" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <span>Send message (Enter)</span>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
    </TooltipProvider>
  );
};
