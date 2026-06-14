import { Activity, AlertTriangle, Bug, ClipboardList, Radio, Server } from "lucide-react";
import { useState } from "react";
import { apiUrl } from "../lib/apiClient";
import { logger, wasLogged } from "../lib/logger";

type DemoAction = {
  id: string;
  title: string;
  body: string;
  icon: typeof Activity;
  run: () => Promise<void> | void;
};

const pause = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

export function LogDemoPage() {
  const [running, setRunning] = useState<string | null>(null);

  const actions: DemoAction[] = [
    {
      id: "basic",
      title: "基础日志",
      body: "写入 debug / info / warn / error 四类前端日志。",
      icon: ClipboardList,
      run: () => {
        logger.debug("Rule editor draft state changed", { rules: 3 });
        logger.info("Ruleset selected", { rulesetId: "finance-v1.2" });
        logger.warn("RAG source has not been refreshed in this session");
        logger.error("Example validation error", new Error("balance_sheet_mismatch"));
      },
    },
    {
      id: "health",
      title: "真实健康检查",
      body: "请求 /api/health，把真实 API 成功或失败写入日志。",
      icon: Server,
      run: async () => {
        const url = apiUrl("/api/health");
        const startedAt = performance.now();
        logger.apiRequest("GET", url);
        try {
          const res = await fetch(url);
          const elapsed = Math.round(performance.now() - startedAt);
          if (!res.ok) throw new Error(`health returned ${res.status}`);
          const payload = await res.json();
          logger.apiResponse("GET", url, res.status, elapsed);
          logger.info("Backend health check returned", payload);
        } catch (error) {
          logger.apiError("GET", url, error, Math.round(performance.now() - startedAt));
        }
      },
    },
    {
      id: "workflow",
      title: "工作流日志",
      body: "展示上传、学习、解释、校验这些阶段的日志形态。",
      icon: Activity,
      run: async () => {
        logger.workflow("upload", "running", "Uploading finance source");
        await pause(260);
        logger.workflow("upload", "done", "Data source registered");
        logger.workflow("learn", "running", "Learning reusable rules");
        await pause(360);
        logger.workflow("learn", "done", "Generated 7 rules");
        logger.workflow("validate", "running", "Checking report against rules");
        await pause(300);
        logger.workflow("validate", "done", "Found 5 violations");
      },
    },
    {
      id: "sse",
      title: "SSE 事件",
      body: "模拟浏览器接收工作流事件时的日志记录。",
      icon: Radio,
      run: async () => {
        logger.sseConnection("connecting", "/api/workflow/events/stream");
        await pause(200);
        logger.sseConnection("connected", "job-visual-demo");
        ["upload", "learn", "explain", "validate"].forEach((stage, index) => {
          logger.sseEvent("workflow", { id: `evt-${index + 1}`, stage, status: "done" });
        });
        logger.sseConnection("disconnected", "job complete");
      },
    },
    {
      id: "errors",
      title: "异常路径",
      body: "记录后端不可用、解析失败、规则命中异常等排障信息。",
      icon: AlertTriangle,
      run: () => {
        const error = new Error("ruleset not found");
        if (!wasLogged(error)) logger.apiError("GET", "/api/rulesets/missing", error);
        logger.warn("SSE handshake timeout; polling will continue");
        logger.error("Workflow result parse failed", new Error("unexpected empty result"));
      },
    },
  ];

  const runAction = async (action: DemoAction) => {
    setRunning(action.id);
    try {
      await action.run();
    } finally {
      setRunning(null);
    }
  };

  const runAll = async () => {
    setRunning("all");
    try {
      for (const action of actions) {
        await action.run();
        await pause(220);
      }
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="log-demo-page">
      <section className="log-demo-hero">
        <span className="section-pill is-cyan">日志系统</span>
        <h1>前后端运行记录可视化</h1>
        <p>
          Jack 分支的日志能力已拆成独立模块接入当前 UI 分支。这里可以触发前端日志、真实健康检查、
          SSE 事件和工作流阶段记录，右下角面板会实时刷新。
        </p>
        <button className="log-demo-primary" type="button" disabled={running !== null} onClick={runAll}>
          <Bug size={16} />
          {running === "all" ? "演示中..." : "一键生成日志"}
        </button>
      </section>

      <section className="log-demo-grid">
        {actions.map((action) => {
          const Icon = action.icon;
          const active = running === action.id || running === "all";
          return (
            <article className="log-demo-card" key={action.id}>
              <span>
                <Icon size={18} />
              </span>
              <h2>{action.title}</h2>
              <p>{action.body}</p>
              <button type="button" disabled={running !== null} onClick={() => runAction(action)}>
                {active ? "执行中" : "执行"}
              </button>
            </article>
          );
        })}
      </section>
    </div>
  );
}
