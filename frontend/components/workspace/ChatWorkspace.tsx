"use client";

import React, { useRef, useEffect } from "react";
import { PanelLeft } from "lucide-react";
import { UserMessage } from "./UserMessage";
import { AssistantMessage } from "./AssistantMessage";
import { ChatComposer } from "./ChatComposer";
import { Message } from "../../types/chat";
import { DataPilotIcon } from "../brand/DataPilotLogo";
import { Button } from "../ui/button";

interface ChatWorkspaceProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  messages: Message[];
  onSendMessage: (message: string) => void;
  isLoading?: boolean;
  userName?: string;
}

export const ChatWorkspace: React.FC<ChatWorkspaceProps> = ({
  isSidebarOpen,
  onToggleSidebar,
  messages,
  onSendMessage,
  isLoading = false,
  userName = "Sohel Islam",
}) => {
  const scrollEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <main className="flex-1 h-screen flex flex-col justify-between bg-[#181A20] overflow-hidden relative">
      {/* Floating Sidebar Open Button (only when sidebar is closed) */}
      {!isSidebarOpen && (
        <div className="absolute top-4 left-4 z-20">
          <Button
            variant="secondary"
            size="sm"
            onClick={onToggleSidebar}
            className="gap-2 text-[#94A3B8] hover:text-white shadow-sm bg-[#1E222B]/90 backdrop-blur-xs"
            aria-label="Open sidebar"
          >
            <PanelLeft className="w-4 h-4" />
            <span className="text-xs font-medium text-[#CBD5E1]">Sidebar</span>
          </Button>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto px-8 pt-8 pb-5 max-w-4xl w-full mx-auto flex flex-col justify-start">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <DataPilotIcon size="lg" className="mb-4" />
            <h2 className="text-xl font-semibold text-white mb-2">
              Ask anything about your data
            </h2>
            <p className="text-sm text-[#94A3B8] max-w-md">
              Ask questions about revenue, user trends, top products, or analytics.
            </p>
          </div>
        ) : (
          messages.map((msg) =>
            msg.role === "user" ? (
              <UserMessage
                key={msg.id}
                content={msg.content}
                timestamp={msg.timestamp}
                userName={userName}
              />
            ) : (
              <AssistantMessage
                key={msg.id}
                content={msg.content}
                timestamp={msg.timestamp}
              />
            )
          )
        )}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex items-start justify-start gap-3 my-3.5 w-full">
            <div className="shrink-0 mt-0.5">
              <DataPilotIcon size="md" />
            </div>
            <div className="bg-[#242834] border border-[#323849] rounded-2xl rounded-tl-xs px-5 py-3.5 shadow-xs flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#FEC50B] animate-pulse" />
              <span
                className="w-2 h-2 rounded-full bg-[#FEC50B] animate-pulse"
                style={{ animationDelay: "200ms" }}
              />
              <span
                className="w-2 h-2 rounded-full bg-[#FEC50B] animate-pulse"
                style={{ animationDelay: "400ms" }}
              />
            </div>
          </div>
        )}

        <div ref={scrollEndRef} />
      </div>

      {/* Compact Composer at bottom */}
      <ChatComposer onSendMessage={onSendMessage} isLoading={isLoading} />
    </main>
  );
};
