"use client";

import React, { useState } from "react";
import { Code2, ChevronDown, ChevronUp, Copy, Check, Table, Zap } from "lucide-react";
import { DataPilotIcon } from "../brand/DataPilotLogo";
import { QueryDataRow } from "../../types/chat";

interface AssistantMessageProps {
  content: string | any;
  timestamp: string;
  sql?: string;
  data?: QueryDataRow[];
  columns?: string[];
  rowCount?: number;
  executionTimeMs?: number;
}

export const AssistantMessage: React.FC<AssistantMessageProps> = ({
  content,
  timestamp,
  sql,
  data,
  columns,
  rowCount,
  executionTimeMs,
}) => {
  const [isSqlOpen, setIsSqlOpen] = useState<boolean>(false);
  const [isTableOpen, setIsTableOpen] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const handleCopySql = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!sql) return;
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy SQL:", err);
    }
  };

  // Helper to format text with bold segments and bullet points
  const renderFormattedContent = (rawContent: any) => {
    const text =
      typeof rawContent === "string"
        ? rawContent
        : typeof rawContent === "object" && rawContent !== null
        ? JSON.stringify(rawContent, null, 2)
        : String(rawContent ?? "");

    const lines = text.split("\n");

    return lines.map((line, lineIdx) => {
      const isBullet = line.trim().startsWith("* ") || line.trim().startsWith("- ");
      const cleanLine = isBullet ? line.trim().replace(/^[\*\-]\s+/, "") : line;

      const parts = cleanLine.split(/(\*\*.*?\*\*)/g);
      const renderedParts = parts.map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={index} className="font-semibold text-white">
              {part.slice(2, -2)}
            </strong>
          );
        }
        return <span key={index}>{part}</span>;
      });

      if (isBullet) {
        return (
          <div key={lineIdx} className="flex items-start gap-2 my-1 pl-1">
            <span className="text-[#FEC50B] font-bold text-xs mt-1.5 leading-none">•</span>
            <div className="flex-1 text-[14px] text-[#F1F5F9] leading-relaxed">
              {renderedParts}
            </div>
          </div>
        );
      }

      return (
        <div
          key={lineIdx}
          className={`text-[14px] text-[#F1F5F9] leading-relaxed ${
            line.trim() === "" ? "h-2" : "my-0.5"
          }`}
        >
          {renderedParts}
        </div>
      );
    });
  };

  const hasData = Array.isArray(data) && data.length > 0;
  const tableColumns = columns && columns.length > 0 ? columns : hasData ? Object.keys(data![0]) : [];

  return (
    <div className="flex items-start justify-start gap-3 my-4 w-full">
      {/* Brand Icon Avatar */}
      <div className="shrink-0 mt-0.5">
        <DataPilotIcon size="md" />
      </div>

      {/* Softer Dark Response Card */}
      <div className="bg-[#242834] border border-[#323849] rounded-2xl rounded-tl-xs px-5 py-4 max-w-[720px] w-full shadow-sm flex flex-col gap-3.5">
        {/* Main Text Content */}
        <div className="select-text">
          {renderFormattedContent(content)}
        </div>

        {/* Action Pills Bar (SQL Toggle & Table Toggle) */}
        {(sql || hasData) && (
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-[#323849]/60">
            {/* View SQL Toggle */}
            {sql && (
              <button
                type="button"
                onClick={() => setIsSqlOpen(!isSqlOpen)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-[#1E222B] hover:bg-[#282E3A] border border-[#323849] text-[#CBD5E1] hover:text-white transition-colors cursor-pointer"
              >
                <Code2 className="w-3.5 h-3.5 text-[#FEC50B]" />
                <span>{isSqlOpen ? "Hide SQL" : "View SQL"}</span>
                {executionTimeMs !== undefined && (
                  <span className="flex items-center gap-0.5 text-[10px] text-[#94A3B8] font-mono ml-0.5">
                    <Zap className="w-2.5 h-2.5 text-[#FEC50B]" />
                    {executionTimeMs}ms
                  </span>
                )}
                {isSqlOpen ? (
                  <ChevronUp className="w-3 h-3 text-[#94A3B8]" />
                ) : (
                  <ChevronDown className="w-3 h-3 text-[#94A3B8]" />
                )}
              </button>
            )}

            {/* View Data Table Toggle */}
            {hasData && (
              <button
                type="button"
                onClick={() => setIsTableOpen(!isTableOpen)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-[#1E222B] hover:bg-[#282E3A] border border-[#323849] text-[#CBD5E1] hover:text-white transition-colors cursor-pointer"
              >
                <Table className="w-3.5 h-3.5 text-[#FEC50B]" />
                <span>{isTableOpen ? "Hide Table" : `Data Table (${rowCount ?? data!.length})`}</span>
                {isTableOpen ? (
                  <ChevronUp className="w-3 h-3 text-[#94A3B8]" />
                ) : (
                  <ChevronDown className="w-3 h-3 text-[#94A3B8]" />
                )}
              </button>
            )}
          </div>
        )}

        {/* Collapsible SQL Block */}
        {sql && isSqlOpen && (
          <div className="bg-[#181A20] border border-[#2E3444] rounded-xl overflow-hidden mt-1">
            <div className="flex items-center justify-between px-3.5 py-2 bg-[#1E222B]/80 border-b border-[#2E3444]">
              <span className="text-[11px] font-mono text-[#94A3B8] uppercase tracking-wider">
                PostgreSQL Query
              </span>
              <button
                type="button"
                onClick={handleCopySql}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-[#CBD5E1] hover:text-white bg-[#282E3A] hover:bg-[#323849] px-2 py-0.5 rounded transition-colors cursor-pointer"
              >
                {copied ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3 text-[#94A3B8]" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
            <pre className="p-3.5 text-[12.5px] font-mono text-[#F1F5F9] whitespace-pre-wrap break-all leading-relaxed overflow-x-auto selection:bg-[#FEC50B]/30">
              <code>{sql}</code>
            </pre>
          </div>
        )}

        {/* Collapsible Data Table */}
        {hasData && isTableOpen && (
          <div className="bg-[#181A20] border border-[#2E3444] rounded-xl overflow-hidden mt-1 max-w-full">
            <div className="overflow-x-auto max-h-64 scrollbar-thin">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#1E222B] border-b border-[#2E3444]">
                    {tableColumns.map((col) => (
                      <th
                        key={col}
                        className="px-3.5 py-2 text-[11px] font-semibold text-[#CBD5E1] uppercase tracking-wider font-mono whitespace-nowrap"
                      >
                        {col.replace(/_/g, " ")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#2E3444]/60">
                  {data!.map((row, idx) => (
                    <tr
                      key={idx}
                      className="hover:bg-[#242834]/60 transition-colors"
                    >
                      {tableColumns.map((col) => {
                        const val = row[col];
                        const isNumber = typeof val === "number";
                        return (
                          <td
                            key={col}
                            className={`px-3.5 py-2 text-[12.5px] text-[#F1F5F9] whitespace-nowrap ${
                              isNumber ? "font-mono text-right" : ""
                            }`}
                          >
                            {val === null || val === undefined
                              ? "-"
                              : isNumber && col.toLowerCase().includes("spend") || col.toLowerCase().includes("revenue") || col.toLowerCase().includes("price") || col.toLowerCase().includes("amount")
                              ? `$${Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                              : String(val)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Timestamp */}
        <span className="text-[11px] text-[#94A3B8] font-normal pt-0.5">
          {timestamp}
        </span>
      </div>
    </div>
  );
};
