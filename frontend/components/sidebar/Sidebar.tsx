"use client";

import React from "react";
import { Plus, ChevronDown, Trash2, PanelLeftClose, User, Settings, LogOut } from "lucide-react";
import { DataPilotLogo } from "../brand/DataPilotLogo";
import { UserAvatar } from "../common/UserAvatar";
import { Conversation } from "../../types/chat";
import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  conversations: Conversation[];
  activeConversationId: string;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onDeleteConversation?: (id: string) => void;
  userName?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggle,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  userName = "Sohel Islam",
}) => {
  if (!isOpen) return null;

  return (
    <aside className="w-[320px] shrink-0 h-screen bg-[#1E222B] border-r border-[#2E3444] flex flex-col justify-between select-none transition-all duration-200 z-30">
      {/* Top Header & New Chat */}
      <div className="p-4 pb-2 flex flex-col gap-3.5 shrink-0">
        {/* Header: Brand and Toggle Button */}
        <div className="flex items-center justify-between pt-1 pb-0.5">
          <DataPilotLogo />
          <Button
            variant="ghost"
            size="iconSm"
            onClick={onToggle}
            aria-label="Close sidebar"
            title="Close sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </Button>
        </div>

        {/* New Chat Button */}
        <Button
          variant="primary"
          onClick={onNewChat}
          className="w-full h-[44px] justify-start px-4 gap-2 text-[14px] font-semibold"
        >
          <Plus className="w-4 h-4 text-[#111827] stroke-[2.5]" />
          <span>New Chat</span>
        </Button>
      </div>

      {/* Conversation List with ScrollArea */}
      <div className="flex-1 min-h-0 px-4 py-2">
        <ScrollArea className="h-full w-full">
          <div className="space-y-1.5 pr-1">
            {conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              return (
                <div
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  className={`group relative flex items-center justify-between px-3.5 py-2.5 rounded-xl cursor-pointer transition-all duration-150 ${
                    isActive
                      ? "bg-[#383115] border border-[#FEC50B]/40 text-white font-medium shadow-xs"
                      : "hover:bg-[#282E3A] text-[#CBD5E1] hover:text-white border border-transparent"
                  }`}
                >
                  <span className="text-[13.5px] truncate flex-1 pr-2">
                    {conv.title || "New Conversation"}
                  </span>

                  {onDeleteConversation && conversations.length > 1 && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteConversation(conv.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 text-[#94A3B8] hover:text-red-400 rounded transition-opacity cursor-pointer shrink-0 ml-1"
                      title="Delete conversation"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </div>

      {/* Bottom User Profile */}
      <div className="p-4 border-t border-[#2E3444] bg-[#1E222B] shrink-0">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <div className="flex items-center justify-between hover:bg-[#282E3A] p-2 rounded-xl cursor-pointer transition-colors outline-none">
              <div className="flex items-center gap-3">
                <UserAvatar name={userName} size="md" />
                <span className="text-[14px] font-medium text-white">
                  {userName}
                </span>
              </div>
              <ChevronDown className="w-4 h-4 text-[#94A3B8]" />
            </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-60 mb-2">
            <DropdownMenuLabel>Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2">
              <User className="w-4 h-4 text-[#94A3B8]" />
              <span>Profile Details</span>
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2">
              <Settings className="w-4 h-4 text-[#94A3B8]" />
              <span>Settings</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2 text-red-400 hover:text-red-300">
              <LogOut className="w-4 h-4" />
              <span>Sign out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  );
};
