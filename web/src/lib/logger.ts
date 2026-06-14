<<<<<<< HEAD
export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LoggerConfig {
  enabled: boolean;
  level: LogLevel;
  prefix: string;
  maxEntries: number;
}

=======
/**
 * logger.ts — NetNomos Forge 前端日志系统
 *
 * 提供轻量级的前端日志功能：
 * - 支持日志级别：debug, info, warn, error
 * - 开发环境启用，生产环境自动禁用
 * - API 请求/响应专用日志方法
 * - 与工作流事件集成
 *
 * @example
 * ```ts
 * import { logger } from '@/lib/logger';
 *
 * logger.info('开始上传文件...', { fileName, size });
 * logger.warn('API返回警告', { warnings });
 * logger.error('处理失败', error);
 * ```
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LoggerConfig {
  enabled: boolean;
  level: LogLevel;
  prefix: string;
}

/**
 * 日志级别优先级（数值越小优先级越高）
 */
const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

/**
 * 控制台方法映射
 */
const CONSOLE_METHODS: Record<LogLevel, keyof Console> = {
  debug: 'log',
  info: 'info',
  warn: 'warn',
  error: 'error',
};

/**
 * 日志记录接口
 */
>>>>>>> origin/Jack
export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
<<<<<<< HEAD
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
=======
  data?: any[];
  prefix: string;
}

/**
 * Logger 类 - 前端日志记录器
 */
class Logger {
  private config: LoggerConfig;
  private logs: LogEntry[] = [];
  private maxLogs = 500; // 最多存储 500 条日志

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = {
      // 开发环境默认启用，生产环境禁用
      enabled: import.meta.env.DEV,
      // 从环境变量读取日志级别，默认 info
      level: (import.meta.env.VITE_LOG_LEVEL as LogLevel) || 'info',
      // 默认前缀
      prefix: '[NetNomos]',
>>>>>>> origin/Jack
      ...config,
    };
  }

<<<<<<< HEAD
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
=======
  /**
   * 判断是否应该记录日志
   */
  private shouldLog(level: LogLevel): boolean {
    if (!this.config.enabled) {
      return false;
    }

    const configLevel = this.config.level;
    const currentLevelPriority = LOG_LEVELS[level];
    const configLevelPriority = LOG_LEVELS[configLevel];

    return currentLevelPriority >= configLevelPriority;
  }

  /**
   * 核心日志方法
   */
  private log(level: LogLevel, message: string, ...args: any[]): void {
    if (!this.shouldLog(level)) {
      return;
    }

    // 生成时间戳
    const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
    const prefix = `${this.config.prefix} [${timestamp}] [${level.toUpperCase()}]`;

    // 获取对应的控制台方法
    const consoleMethod = CONSOLE_METHODS[level];

    // 输出到控制台
    console[consoleMethod](prefix, message, ...args);

    // 存储到内存中
    const logEntry: LogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      level,
      message,
      data: args.length > 0 ? args : undefined,
      prefix: this.config.prefix,
    };

    this.addLog(logEntry);
  }

  /**
   * 添加日志到内存中
   */
  private addLog(logEntry: LogEntry): void {
    this.logs.push(logEntry);

    // 保持日志数量在限制内
    if (this.logs.length > this.maxLogs) {
      this.logs.shift(); // 删除最旧的日志
    }
  }

  /**
   * DEBUG 级别日志
   */
  debug(message: string, ...args: any[]): void {
    this.log('debug', message, ...args);
  }

  /**
   * INFO 级别日志
   */
  info(message: string, ...args: any[]): void {
    this.log('info', message, ...args);
  }

  /**
   * WARN 级别日志
   */
  warn(message: string, ...args: any[]): void {
    this.log('warn', message, ...args);
  }

  /**
   * ERROR 级别日志
   */
  error(message: string, ...args: any[]): void {
    this.log('error', message, ...args);
  }

  /**
   * API 请求日志
   */
  apiRequest(method: string, url: string, body?: any): void {
    this.debug(`📡 API ${method} ${url}`, body ? { body } : '');
  }

  /**
   * API 响应日志
   */
  apiResponse(method: string, url: string, status: number, duration: number): void {
    this.debug(`📡 API ${method} ${url} | ${status} | ${duration}ms`);
  }

  /**
   * API 错误日志
   */
  apiError(method: string, url: string, error: Error): void {
    this.error(`📡 API ${method} ${url} FAILED`, error.message);
  }

  /**
   * SSE 事件日志
   */
  sseEvent(eventType: string, data?: any): void {
    this.debug(`📨 SSE ${eventType}`, data || '');
  }

  /**
   * SSE 连接状态日志
   */
  sseConnection(status: 'connecting' | 'connected' | 'disconnected' | 'error', url?: string): void {
    const message = url ? `🔌 SSE ${status} (${url})` : `🔌 SSE ${status}`;
    this.debug(message);
  }

  /**
   * 工作流事件日志
   */
  workflow(stage: string, status: string, description: string): void {
    this.info(`⚙️ 工作流 [${stage}] ${status}: ${description}`);
  }

  /**
   * 动态设置日志级别
   */
  setLevel(level: LogLevel): void {
    this.config.level = level;
    this.info(`🎚️ 日志级别已设置为: ${level.toUpperCase()}`);
  }

  /**
   * 动态启用/禁用日志
   */
  setEnabled(enabled: boolean): void {
    this.config.enabled = enabled;
    this.info(`🔧 日志已${enabled ? '启用' : '禁用'}`);
  }

  /**
   * 获取所有日志
   */
  getLogs(): LogEntry[] {
    return [...this.logs]; // 返回副本
  }

  /**
   * 清空日志
   */
  clearLogs(): void {
    this.logs = [];
    this.info('🗑️ 日志已清空');
  }

  /**
   * 根据级别过滤日志
   */
  getLogsByLevel(level: LogLevel): LogEntry[] {
    return this.logs.filter(log => log.level === level);
  }

  /**
   * 获取最近的日志
   */
  getRecentLogs(count: number = 50): LogEntry[] {
    return this.logs.slice(-count);
  }
}

/**
 * 默认 Logger 实例
 */
export const logger = new Logger();

/**
 * 创建命名的 Logger 实例
 *
 * @param name - logger 名称（用作前缀）
 * @returns 新的 Logger 实例
 *
 * @example
 * ```ts
 * const apiLogger = createLogger('API');
 * apiLogger.info('Fetching data...');
 * // 输出: [API] [18:02:25] [INFO] Fetching data...
 * ```
 */
export function createLogger(name: string): Logger {
  return new Logger({
    prefix: `[${name}]`,
    enabled: import.meta.env.DEV,
    level: (import.meta.env.VITE_LOG_LEVEL as LogLevel) || 'info',
  });
}

/**
 * 导出类型
 */
export type { LogLevel, LoggerConfig };
>>>>>>> origin/Jack
