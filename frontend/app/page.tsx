"use client";

import { useState } from "react";
import { Sidebar } from "../components/sidebar/Sidebar";
import { ChatWorkspace } from "../components/workspace/ChatWorkspace";
import { Conversation, Message } from "../types/chat";

const formatCurrentTime = (): string => {
  const now = new Date();
  let hours = now.getHours();
  const minutes = now.getMinutes().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12;
  hours = hours ? hours : 12;
  return `${hours}:${minutes} ${ampm}`;
};

const INITIAL_CONVERSATIONS: Conversation[] = [
  {
    id: "conv-1",
    title: "New Conversation",
    timestamp: formatCurrentTime(),
    messages: [],
  },
];

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [conversations, setConversations] = useState<Conversation[]>(
    INITIAL_CONVERSATIONS
  );
  const [activeConversationId, setActiveConversationId] = useState<string>(
    INITIAL_CONVERSATIONS[0].id
  );
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const activeConversation =
    conversations.find((c) => c.id === activeConversationId) ||
    conversations[0];

  const handleToggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const handleNewChat = () => {
    const newId = `conv-${Date.now()}`;
    const newConversation: Conversation = {
      id: newId,
      title: "New Conversation",
      timestamp: formatCurrentTime(),
      messages: [],
    };
    setConversations((prev) => [newConversation, ...prev]);
    setActiveConversationId(newId);
  };

  const handleSelectConversation = (id: string) => {
    setActiveConversationId(id);
  };

  const handleDeleteConversation = (id: string) => {
    setConversations((prev) => {
      const filtered = prev.filter((c) => c.id !== id);
      if (activeConversationId === id && filtered.length > 0) {
        setActiveConversationId(filtered[0].id);
      }
      return filtered;
    });
  };

  const handleSendMessage = async (text: string) => {
    const timeStr = formatCurrentTime();
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: timeStr,
    };

    // Update conversation with user message & update title if first message
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id === activeConversationId) {
          const isFirstMessage = c.messages.length === 0;
          return {
            ...c,
            title: isFirstMessage ? text : c.title,
            timestamp: timeStr,
            messages: [...c.messages, userMessage],
          };
        }
        return c;
      })
    );

    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();

      // Safely extract string response from various possible API formats
      let assistantText = "";
      if (typeof data === "string") {
        assistantText = data;
      } else if (typeof data?.response === "string") {
        assistantText = data.response;
      } else if (Array.isArray(data?.response)) {
        assistantText = data.response
          .map((item: any) =>
            typeof item === "string"
              ? item
              : item?.text || JSON.stringify(item)
          )
          .join("\n");
      } else if (data?.response && typeof data.response === "object") {
        assistantText =
          data.response.content || JSON.stringify(data.response, null, 2);
      } else {
        assistantText = String(
          data?.response ?? data?.detail ?? "No response received from assistant."
        );
      }

      const assistantMessage: Message = {
        id: `msg-${Date.now() + 1}`,
        role: "assistant",
        content: assistantText,
        timestamp: formatCurrentTime(),
        sql: data?.sql,
        data: data?.data,
        columns: data?.columns,
        rowCount: data?.row_count,
        executionTimeMs: data?.execution_time_ms,
      };

      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId
            ? { ...c, messages: [...c.messages, assistantMessage] }
            : c
        )
      );
    } catch (error) {
      console.error("Failed to fetch response from backend:", error);

      const fallbackMessage: Message = {
        id: `msg-${Date.now() + 1}`,
        role: "assistant",
        content:
          "I received your question. (Backend service is currently connecting at http://localhost:8000)",
        timestamp: formatCurrentTime(),
      };

      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId
            ? { ...c, messages: [...c.messages, fallbackMessage] }
            : c
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#181A20] text-[#F4F4F5]">
      {/* Left Collapsible Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onToggle={handleToggleSidebar}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        userName="Sohel Islam"
      />

      {/* Main Workspace */}
      <ChatWorkspace
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={handleToggleSidebar}
        messages={activeConversation?.messages || []}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        userName="Sohel Islam"
      />
    </div>
  );
}
