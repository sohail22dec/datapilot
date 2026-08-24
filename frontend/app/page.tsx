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
      if (filtered.length === 0) {
        const freshId = `conv-${Date.now()}`;
        const freshConv: Conversation = {
          id: freshId,
          title: "New Conversation",
          timestamp: formatCurrentTime(),
          messages: [],
        };
        setActiveConversationId(freshId);
        return [freshConv];
      }
      if (activeConversationId === id) {
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

    const assistantMsgId = `msg-${Date.now() + 1}`;
    const initialAssistantMessage: Message = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      timestamp: timeStr,
      isStreaming: true,
      steps: ["Analyzing inquiry & schema..."],
    };

    // Update conversation with user message & streaming assistant message
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id === activeConversationId) {
          const isFirstMessage = c.messages.length === 0;
          return {
            ...c,
            title: isFirstMessage ? text : c.title,
            timestamp: timeStr,
            messages: [...c.messages, userMessage, initialAssistantMessage],
          };
        }
        return c;
      })
    );

    setIsLoading(true);

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

    try {
      const response = await fetch(`${backendUrl}/api/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error("No readable stream received from backend.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";
      let accumulatedText = "";
      const accumulatedSteps: string[] = ["🔍 Analyzing Inquiry & Schema"];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("event:")) {
            currentEvent = trimmed.replace("event:", "").trim();
          } else if (trimmed.startsWith("data:")) {
            const rawData = trimmed.replace("data:", "").trim();
            if (!rawData) continue;

            try {
              const parsed = JSON.parse(rawData);

              if (currentEvent === "step" || parsed.step || parsed.badge) {
                const stepText = parsed.badge || parsed.step || "Processing...";
                if (!accumulatedSteps.includes(stepText)) {
                  accumulatedSteps.push(stepText);
                }

                setConversations((prev) =>
                  prev.map((c) =>
                    c.id === activeConversationId
                      ? {
                          ...c,
                          messages: c.messages.map((m) =>
                            m.id === assistantMsgId
                              ? {
                                  ...m,
                                  steps: [...accumulatedSteps],
                                  sql: parsed.sql || m.sql,
                                }
                              : m
                          ),
                        }
                      : c
                  )
                );
              } else if (currentEvent === "token" || parsed.delta) {
                const delta = parsed.delta || "";
                accumulatedText += delta;

                setConversations((prev) =>
                  prev.map((c) =>
                    c.id === activeConversationId
                      ? {
                          ...c,
                          messages: c.messages.map((m) =>
                            m.id === assistantMsgId
                              ? {
                                  ...m,
                                  content: accumulatedText,
                                }
                              : m
                          ),
                        }
                      : c
                  )
                );
              } else if (currentEvent === "done" || parsed.response !== undefined) {
                setConversations((prev) =>
                  prev.map((c) =>
                    c.id === activeConversationId
                      ? {
                          ...c,
                          messages: c.messages.map((m) =>
                            m.id === assistantMsgId
                              ? {
                                  ...m,
                                  content: parsed.response || accumulatedText,
                                  sql: parsed.sql,
                                  data: parsed.data,
                                  columns: parsed.columns,
                                  rowCount: parsed.row_count,
                                  executionTimeMs: parsed.execution_time_ms,
                                  chartConfig: parsed.chart_config,
                                  thoughtTrace: parsed.thought_trace,
                                  isStreaming: false,
                                }
                              : m
                          ),
                        }
                      : c
                  )
                );
              }
            } catch (err) {
              console.error("Error parsing SSE data line:", err, rawData);
            }
          }
        }
      }
    } catch (error) {
      console.error("Failed to fetch response from backend:", error);

      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId
            ? {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === assistantMsgId
                    ? {
                        ...m,
                        content:
                          `I encountered an issue connecting to the backend service. Please check your backend connection at ${backendUrl}.`,
                        isStreaming: false,
                      }
                    : m
                ),
              }
            : c
        )
      );
    } finally {
      setIsLoading(false);
      // Ensure streaming flag is cleared
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId
            ? {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === assistantMsgId
                    ? { ...m, isStreaming: false }
                    : m
                ),
              }
            : c
        )
      );
    }
  };

  return (
    <div className="flex h-screen w-screen bg-[#181A20] text-slate-100 overflow-hidden font-sans antialiased">
      {/* Collapsible Left Sidebar */}
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

      {/* Main Workspace Area */}
      <ChatWorkspace
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={handleToggleSidebar}
        messages={activeConversation.messages}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        userName="Sohel Islam"
      />
    </div>
  );
}
