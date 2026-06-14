export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LoggerConfig {
  enabled: boolean;
  level: LogLevel;
  prefix: string;
  maxEntries: number;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: unknown[];
  prefix: string;
}

type Listener = (entries: LogEntry[]) => void;

const LEVEL_WEIGHT: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

const CONSOLE_METHOD: Record<LogLevel, "debug" | "info" | "warn" | "error"> = {
  debug: "debug",
  info: "info",
  warn: "warn",
  error: "error",
};

function envFlag(value: unknown): boolean {
  return String(value ?? "").toLowerCase() === "true";
}

function normalizeLevel(level: unknown): LogLevel {
  return level === "debug" || level === "warn" || level === "error" ? level : "info";
}

function markLogged(error: unknown): void {
  if (error && typeof error === "object") {
    (error as { __netnomosLogged?: boolean }).__netnomosLogged = true;
  }
}

export function wasLogged(error: unknown): boolean {
  return Boolean(error && typeof error === "object" && (error as { __netnomosLogged?: boolean }).__netnomosLogged);
}

class Logger {
  private config: LoggerConfig;
  private entries: LogEntry[] = [];
  private listeners = new Set<Listener>();

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = {
      enabled: import.meta.env.DEV || envFlag(import.meta.env.VITE_ENABLE_FRONTEND_LOGS),
      level: normalizeLevel(import.meta.env.VITE_LOG_LEVEL),
      prefix: "NetNomos",
      maxEntries: 500,
      ...config,
    };
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.getLogs());
    return () => this.listeners.delete(listener);
  }

  getLogs(): LogEntry[] {
    return [...this.entries];
  }

  getLogsByLevel(level: LogLevel): LogEntry[] {
    return this.entries.filter((entry) => entry.level === level);
  }

  clearLogs(): void {
    this.entries = [];
    this.emit();
  }

  setLevel(level: LogLevel): void {
    this.config.level = level;
    this.info(`Log level changed to ${level}`);
  }

  setEnabled(enabled: boolean): void {
    this.config.enabled = enabled;
    if (enabled) this.info("Frontend logging enabled");
  }

  debug(message: string, ...data: unknown[]): void {
    this.write("debug", message, data);
  }

  info(message: string, ...data: unknown[]): void {
    this.write("info", message, data);
  }

  warn(message: string, ...data: unknown[]): void {
    this.write("warn", message, data);
  }

  error(message: string, error?: unknown, ...data: unknown[]): void {
    if (error instanceof Error) markLogged(error);
    this.write("error", message, error === undefined ? data : [error, ...data]);
  }

  apiRequest(method: string, url: string, data?: unknown): void {
    this.debug(`API ${method.toUpperCase()} ${url}`, data);
  }

  apiResponse(method: string, url: string, status: number, durationMs: number): void {
    this.debug(`API ${method.toUpperCase()} ${url} -> ${status} (${durationMs}ms)`);
  }

  apiError(method: string, url: string, error: unknown, durationMs?: number): void {
    if (error instanceof Error) markLogged(error);
    const suffix = typeof durationMs === "number" ? ` (${durationMs}ms)` : "";
    this.write("error", `API ${method.toUpperCase()} ${url} failed${suffix}`, [error]);
  }

  sseConnection(status: "connecting" | "connected" | "disconnected" | "error", detail?: unknown): void {
    this.debug(`SSE ${status}`, detail);
  }

  sseEvent(eventType: string, data?: unknown): void {
    this.debug(`SSE event: ${eventType}`, data);
  }

  workflow(stage: string, status: string, description: string): void {
    this.info(`Workflow ${stage} ${status}: ${description}`);
  }

  private write(level: LogLevel, message: string, data: unknown[]): void {
    if (!this.shouldLog(level)) return;
    const entry: LogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: new Date().toISOString(),
      level,
      message,
      data: data.length > 0 ? data : undefined,
      prefix: this.config.prefix,
    };
    this.entries = [...this.entries, entry].slice(-this.config.maxEntries);
    const method = CONSOLE_METHOD[level];
    console[method](`[${this.config.prefix}] [${level.toUpperCase()}] ${message}`, ...(entry.data ?? []));
    this.emit();
  }

  private shouldLog(level: LogLevel): boolean {
    return this.config.enabled && LEVEL_WEIGHT[level] >= LEVEL_WEIGHT[this.config.level];
  }

  private emit(): void {
    const snapshot = this.getLogs();
    this.listeners.forEach((listener) => listener(snapshot));
  }
}

export const logger = new Logger();

export function createLogger(name: string): Logger {
  return new Logger({ prefix: name });
}
