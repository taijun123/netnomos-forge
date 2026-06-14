import { ChevronDown, ChevronUp, ClipboardList, Pause, Play, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { logger, type LogEntry, type LogLevel } from "../lib/logger";

const LEVELS: Array<LogLevel | "all"> = ["all", "debug", "info", "warn", "error"];

const LEVEL_LABEL: Record<LogLevel | "all", string> = {
  all: "全部",
  debug: "调试",
  info: "信息",
  warn: "警告",
  error: "错误",
};

function serializeData(entry: LogEntry): string {
  if (!entry.data || entry.data.length === 0) return "";
  return entry.data
    .map((item) => {
      if (item instanceof Error) return item.message;
      if (typeof item === "string") return item;
      try {
        return JSON.stringify(item, null, 2);
      } catch {
        return String(item);
      }
    })
    .filter(Boolean)
    .join("\n");
}

function formatTime(timestamp: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(timestamp));
}

export function LogPanel() {
  const [entries, setEntries] = useState<LogEntry[]>(() => logger.getLogs());
  const [filter, setFilter] = useState<LogLevel | "all">("all");
  const [expanded, setExpanded] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => logger.subscribe(setEntries), []);

  const filteredEntries = useMemo(
    () => (filter === "all" ? entries : entries.filter((entry) => entry.level === filter)),
    [entries, filter]
  );

  useEffect(() => {
    if (!autoScroll || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [filteredEntries.length, autoScroll]);

  return (
    <section className="log-panel" aria-label="系统日志">
      <header className="log-panel-head">
        <div>
          <span>
            <ClipboardList size={16} />
          </span>
          <strong>系统日志</strong>
          <em>{filteredEntries.length} 条</em>
        </div>
        <button type="button" onClick={() => setExpanded((value) => !value)} title={expanded ? "收起" : "展开"}>
          {expanded ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </button>
      </header>

      {expanded && (
        <>
          <div className="log-panel-tools">
            <div className="log-level-tabs" role="tablist" aria-label="日志级别">
              {LEVELS.map((level) => (
                <button
                  key={level}
                  type="button"
                  className={`is-${level}${filter === level ? " is-active" : ""}`}
                  onClick={() => setFilter(level)}
                >
                  {LEVEL_LABEL[level]}
                </button>
              ))}
            </div>
            <div className="log-panel-actions">
              <button
                type="button"
                onClick={() => setAutoScroll((value) => !value)}
                title={autoScroll ? "暂停自动滚动" : "开启自动滚动"}
              >
                {autoScroll ? <Pause size={14} /> : <Play size={14} />}
              </button>
              <button type="button" onClick={() => logger.clearLogs()} title="清空日志">
                <Trash2 size={14} />
              </button>
            </div>
          </div>

          <div className="log-panel-body" ref={scrollRef}>
            {filteredEntries.length === 0 ? (
              <p className="log-empty">暂无日志。运行工作流或打开日志演示后会显示实时记录。</p>
            ) : (
              filteredEntries.map((entry) => {
                const details = serializeData(entry);
                return (
                  <article className={`log-entry is-${entry.level}`} key={entry.id}>
                    <span>{formatTime(entry.timestamp)}</span>
                    <strong>{entry.level.toUpperCase()}</strong>
                    <p>{entry.message}</p>
                    {details && <pre>{details}</pre>}
                  </article>
                );
              })
            )}
          </div>
        </>
      )}
    </section>
  );
}
