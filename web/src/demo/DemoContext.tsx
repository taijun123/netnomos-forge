// 全局「自动演示」状态，跨路由共享。顶栏/办公室入口写入(startDemo)，各页订阅(useDemo)。
import { createContext, useContext, useState, type ReactNode } from "react";
import type { DemoScenario } from "./demoAssets";

export type DemoMode = null | "network" | "finance" | "office";

export interface OfficeSummary {
  scenario: DemoScenario;
  learnedRules: number;
  cardCount: number;
  violations: number;
  trackAViolations: number;
  trackBViolations: number;
  dualTitle?: string;
}

interface DemoState {
  mode: DemoMode;
  officeScenario: DemoScenario | null;
  runToken: number; // 每次启动自增，作为各页 useEffect 依赖，保证重复触发可重跑
  status: "idle" | "running" | "done" | "error";
  startDemo: (mode: Exclude<DemoMode, null>, sub?: DemoScenario) => void;
  stopDemo: () => void;
  setStatus: (s: DemoState["status"]) => void;
  officeSummary: OfficeSummary | null;
  setOfficeSummary: (s: OfficeSummary | null) => void;
}

const Ctx = createContext<DemoState | null>(null);

export function DemoProvider({
  children,
  navigate,
}: {
  children: ReactNode;
  navigate: (r: "network" | "finance" | "office") => void;
}) {
  const [mode, setMode] = useState<DemoMode>(null);
  const [officeScenario, setOfficeScenario] = useState<DemoScenario | null>(null);
  const [runToken, setRunToken] = useState(0);
  const [status, setStatus] = useState<DemoState["status"]>("idle");
  const [officeSummary, setOfficeSummary] = useState<OfficeSummary | null>(null);

  const startDemo = (m: Exclude<DemoMode, null>, sub?: DemoScenario) => {
    setMode(m);
    setOfficeScenario(m === "office" ? sub ?? "network" : null);
    setStatus("running");
    setRunToken((t) => t + 1);
    navigate(m === "office" ? "office" : m);
  };

  const stopDemo = () => {
    setMode(null);
    setStatus("idle");
  };

  return (
    <Ctx.Provider
      value={{ mode, officeScenario, runToken, status, startDemo, stopDemo, setStatus, officeSummary, setOfficeSummary }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useDemo(): DemoState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useDemo 必须在 DemoProvider 内使用");
  return v;
}
