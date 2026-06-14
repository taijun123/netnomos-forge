import { motion } from "framer-motion";
import { Box, CheckCircle2, CircleDashed, Network, Settings2, Shield } from "lucide-react";
import type { Agent, RuleGroup, WorkflowEvent } from "../types/domain";
import { agentNameMap, seedRuleSet } from "../data/mockData";

interface StatusPanelProps {
  agents: Agent[];
  events: WorkflowEvent[];
  ruleGroups: RuleGroup[];
  rulesLoaded: boolean;
  dataLoaded: boolean;
  onOpenPacket: () => void;
  onOpenRules: () => void;
}

const statusLabel = {
  pending: "等待",
  running: "运行中",
  done: "完成",
  blocked: "阻塞",
};

export function StatusPanel({
  agents,
  events,
  ruleGroups,
  rulesLoaded,
  dataLoaded,
  onOpenPacket,
  onOpenRules,
}: StatusPanelProps) {
  const activeCount = agents.filter((agent) => agent.status !== "idle").length;
  const totalRules = ruleGroups.reduce((n, g) => n + g.rules.length, 0);
  const enabledRules = ruleGroups.reduce((n, g) => n + g.rules.filter((r) => r.enabled).length, 0);

  return (
    <aside className="status-panel">
      <section className="metric-strip" aria-label="总体指标">
        <div>
          <span>活跃员工</span>
          <strong>{activeCount}</strong>
        </div>
        <div>
          <span>规则状态</span>
          <strong>{rulesLoaded ? "监管中" : "待上传"}</strong>
        </div>
        <div>
          <span>数据流</span>
          <strong>{dataLoaded ? "派送中" : "待目录"}</strong>
        </div>
      </section>

      <section className="rules-card">
        <div className="section-title">
          <Shield size={16} />
          <h2>当前规则集</h2>
          <button className="rules-manage" onClick={onOpenRules}>
            <Settings2 size={13} />
            查看 / 新建
          </button>
        </div>
        <div className="rule-header">
          <strong>{seedRuleSet.name}</strong>
          <span className={rulesLoaded ? "badge badge-ok" : "badge"}>{rulesLoaded ? "已接入" : "未接入"}</span>
        </div>
        <ul className="rule-group-overview">
          {ruleGroups.map((group) => (
            <li key={group.id}>
              <span className="rule-group-dot" />
              <b>{group.name}</b>
              <em>
                {group.rules.filter((r) => r.enabled).length}/{group.rules.length}
              </em>
            </li>
          ))}
        </ul>
        <button className="rules-card-more" onClick={onOpenRules}>
          共 {ruleGroups.length} 组 / {totalRules} 条 · 启用 {enabledRules} 条 · 点击管理 ›
        </button>
      </section>

      <section className="pipeline-card">
        <div className="section-title">
          <CircleDashed size={16} />
          <h2>流程队列</h2>
        </div>
        <div className="pipeline">
          {["上传", "分析", "验证", "插件", "受控输出"].map((step, index) => (
            <div
              className={`pipeline-step ${
                index < (rulesLoaded ? 1 : 0) + (dataLoaded ? 3 : 0) ? "is-complete" : ""
              }`}
              key={step}
            >
              <span>{index + 1}</span>
              <small>{step}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="event-card">
        <div className="section-title">
          <CheckCircle2 size={16} />
          <h2>任务日志</h2>
        </div>
        <div className="event-list">
          {events.slice(0, 7).map((event, index) => (
            <motion.div
              className="event-row"
              key={event.id}
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.03 }}
            >
              <span className={`event-dot event-dot--${event.status}`} />
              <div>
                <strong>{event.stage}</strong>
                <p>{event.description}</p>
                <small>
                  {event.time} · {agentNameMap[event.agent]} · {statusLabel[event.status]}
                </small>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      <button className="packet-shortcut" onClick={onOpenPacket} disabled={!dataLoaded}>
        <Network size={16} />
        <span>{dataLoaded ? "打开快递B抓包界面" : "数据派送后可抓包"}</span>
      </button>

      <section className="artifact-card">
        <Box size={16} />
        <div>
          <strong>rule_guard_v03.zip</strong>
          <span>插件制品演示位</span>
        </div>
      </section>
    </aside>
  );
}
