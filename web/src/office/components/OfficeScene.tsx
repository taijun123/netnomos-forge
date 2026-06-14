import { Database, ShieldCheck } from "lucide-react";
import type { Agent, AgentId } from "../types/domain";
import { Office3DScene } from "./Office3DScene";
import { DemoStartMenu } from "../../demo/DemoStartMenu";
import type { DemoScenario } from "../../demo/demoAssets";

interface OfficeSceneProps {
  agents: Agent[];
  rulesLoaded: boolean;
  dataLoaded: boolean;
  onAgentDoubleClick: (agentId: AgentId) => void;
  onLaunchDemo: (scenario: DemoScenario) => void;
}

export function OfficeScene({
  agents,
  rulesLoaded,
  dataLoaded,
  onAgentDoubleClick,
  onLaunchDemo,
}: OfficeSceneProps) {
  return (
    <main className="office-shell">
      <header className="office-header">
        <div>
          <h1>规则智能体办公室</h1>
          <p>
            用 3D 俯视房屋布局展示主管监管、pcap/csv 数据配送、规则分析验证、插件制作与受控模型输出。
          </p>
        </div>
        <div className="header-actions">
          <DemoStartMenu
            variant="office"
            includeOffice={false}
            onPick={(_, sub) => onLaunchDemo(sub ?? "network")}
          />
          <span className={rulesLoaded ? "state-pill is-on" : "state-pill"}>
            <ShieldCheck size={14} />
            {rulesLoaded ? "主管监管中" : "等待规则集"}
          </span>
          <span className={dataLoaded ? "state-pill is-on" : "state-pill"}>
            <Database size={14} />
            {dataLoaded ? "数据已加载" : "数据未上传"}
          </span>
        </div>
      </header>

      <Office3DScene
        agents={agents}
        rulesLoaded={rulesLoaded}
        dataLoaded={dataLoaded}
        onAgentDoubleClick={onAgentDoubleClick}
      />
    </main>
  );
}
