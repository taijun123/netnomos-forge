<<<<<<< HEAD
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
=======
/**
 * LogPanel.tsx — 系统日志面板组件
 *
 * 提供用户友好的日志查看界面：
 * - 实时显示系统日志
 * - 支持按级别过滤
 * - 自动滚动到最新日志
 * - 支持清空日志
 * - 美观的卡片式布局
 *
 * @example
 * ```tsx
 * <LogPanel />
 * ```
 */
import React, { useState, useEffect, useRef } from 'react';
import { logger, type LogEntry, type LogLevel } from '../lib/logger';

const LOG_LEVELS: LogLevel[] = ['debug', 'info', 'warn', 'error'];

const LEVEL_COLORS: Record<LogLevel, string> = {
  debug: 'text-gray-600',
  info: 'text-blue-600',
  warn: 'text-yellow-600',
  error: 'text-red-600',
};

const LEVEL_ICONS: Record<LogLevel, string> = {
  debug: '🔍',
  info: 'ℹ️',
  warn: '⚠️',
  error: '❌',
};

const LEVEL_LABELS: Record<LogLevel, string> = {
  debug: '调试',
  info: '信息',
  warn: '警告',
  error: '错误',
};

export function LogPanel() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<LogLevel | 'all'>('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // 定期更新日志
  useEffect(() => {
    const updateLogs = () => {
      const allLogs = logger.getLogs();
      const filteredLogs = filter === 'all'
        ? allLogs
        : allLogs.filter(log => log.level === filter);
      setLogs(filteredLogs);

      // 自动滚动到底部
      if (autoScroll && logContainerRef.current) {
        logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
      }
    };

    // 初始加载
    updateLogs();

    // 定期更新（每秒）
    const interval = setInterval(updateLogs, 1000);

    return () => clearInterval(interval);
  }, [filter, autoScroll]);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', { hour12: false });
  };

  const clearLogs = () => {
    logger.clearLogs();
    setLogs([]);
  };

  const getLogCount = (level: LogLevel) => {
    return logger.getLogsByLevel(level).length;
  };

  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
      {/* 头部 */}
      <div className="bg-gradient-to-r from-blue-500 to-purple-500 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-white font-semibold text-lg">📋 系统日志</span>
          <span className="bg-white/20 text-white text-xs px-2 py-1 rounded-full">
            {logs.length} 条
          </span>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-white hover:bg-white/20 px-3 py-1 rounded transition"
        >
          {expanded ? '▼' : '▲'}
        </button>
      </div>

      {/* 过滤器 */}
      {expanded && (
        <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-gray-600">过滤级别:</span>
            {LOG_LEVELS.map(level => (
              <button
                key={level}
                onClick={() => setFilter(filter === level ? 'all' : level)}
                className={`px-3 py-1 rounded-full text-sm transition ${
                  filter === level
                    ? `bg-${level === 'error' ? 'red' : level === 'warn' ? 'yellow' : level === 'info' ? 'blue' : 'gray'}-500 text-white`
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {LEVEL_ICONS[level]} {LEVEL_LABELS[level]}
                {getLogCount(level) > 0 && ` (${getLogCount(level)})`}
              </button>
            ))}
            {filter !== 'all' && (
              <button
                onClick={() => setFilter('all')}
                className="px-3 py-1 rounded-full text-sm bg-purple-500 text-white hover:bg-purple-600 transition"
              >
                显示全部
              </button>
            )}
          </div>

          <div className="flex items-center gap-4 mt-3">
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="rounded"
              />
              自动滚动
            </label>
            <button
              onClick={clearLogs}
              className="text-sm text-red-600 hover:text-red-800 transition"
            >
              🗑️ 清空日志
            </button>
          </div>
        </div>
      )}

      {/* 日志内容 */}
      {expanded && (
        <div
          ref={logContainerRef}
          className="bg-gray-900 p-4 overflow-y-auto"
          style={{ maxHeight: '400px', fontFamily: 'monospace', fontSize: '13px' }}
        >
          {logs.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              暂无日志记录
            </div>
          ) : (
            <div className="space-y-1">
              {logs.map(log => (
                <div
                  key={log.id}
                  className={`py-1 px-2 rounded ${
                    log.level === 'error' ? 'bg-red-900/30' :
                    log.level === 'warn' ? 'bg-yellow-900/30' :
                    log.level === 'info' ? 'bg-blue-900/30' :
                    'bg-gray-800/50'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-gray-500 shrink-0">{formatTime(log.timestamp)}</span>
                    <span className={`font-semibold shrink-0 ${
                      log.level === 'error' ? 'text-red-400' :
                      log.level === 'warn' ? 'text-yellow-400' :
                      log.level === 'info' ? 'text-blue-400' :
                      'text-gray-400'
                    }`}>
                      [{log.level.toUpperCase()}]
                    </span>
                    <span className="text-gray-300">{log.message}</span>
                    {log.data && log.data.length > 0 && (
                      <div className="ml-6 mt-1 text-gray-500 text-xs">
                        {JSON.stringify(log.data, null, 2)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
>>>>>>> origin/Jack
  );
}
