import {
  Activity,
  Bot,
  Boxes,
  ClipboardCheck,
  Database,
  MessageCircle,
  Settings,
} from "lucide-react";
import type { CSSProperties } from "react";
import type { Agent, AgentId, AgentStatus } from "../types/domain";
import { CatAvatar } from "./CatAvatar";

const groups = [
  {
    title: "工作台",
    items: [
      { icon: Bot, label: "智能体办公室", nav: "office", active: true },
      { icon: Activity, label: "流程状态", nav: "office" },
      { icon: MessageCircle, label: "手机沟通", nav: "phone" },
    ],
  },
  {
    title: "规则链路",
    items: [
      { icon: ClipboardCheck, label: "规则集", nav: "rules" },
      { icon: Database, label: "数据", nav: "data" },
      { icon: Boxes, label: "产出物", nav: "outputs" },
    ],
  },
] as const;

const STATUS_META: Record<AgentStatus, { label: string; tone: "idle" | "active" }> = {
  idle: { label: "待命", tone: "idle" },
  supervising: { label: "监管中", tone: "active" },
  delivering: { label: "配送中", tone: "active" },
  analyzing: { label: "分析中", tone: "active" },
  validating: { label: "验证中", tone: "active" },
  building: { label: "打包中", tone: "active" },
  reviewing: { label: "待沟通", tone: "active" },
};

interface SidebarProps {
  agents: Agent[];
  activeAgentId?: AgentId | null;
  onSelectAgent: (id: AgentId) => void;
  onNav: (key: string) => void;
}

export function Sidebar({ agents, activeAgentId, onSelectAgent, onNav }: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="侧边导航">
      <div className="brand">
        <div className="brand-mark">R</div>
        <div>
          <strong>Rule Office</strong>
          <span>多智能体原型</span>
        </div>
      </div>
      <div className="nav-groups">
        {groups.map((group) => (
          <nav key={group.title}>
            <p>{group.title}</p>
            {group.items.map((item) => (
              <button
                key={item.label}
                className={`nav-item ${"active" in item && item.active ? "is-active" : ""}`}
                onClick={() => onNav(item.nav)}
              >
                <item.icon size={15} />
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        ))}
      </div>

      <div className="roster" aria-label="团队成员">
        <p className="roster-title">团队成员</p>
        {agents.map((agent) => {
          const meta = STATUS_META[agent.status];
          return (
            <button
              key={agent.id}
              className={`roster-item ${activeAgentId === agent.id ? "is-active" : ""}`}
              style={{ "--agent-color": agent.color } as CSSProperties}
              onClick={() => onSelectAgent(agent.id)}
              title={`${agent.name} · ${agent.role}`}
            >
              <span className="roster-avatar">
                <CatAvatar color={agent.color} size={30} radius={9} />
                <i className={`roster-presence roster-presence--${meta.tone}`} />
              </span>
              <span className="roster-info">
                <strong>{agent.code}</strong>
                <small>{agent.role}</small>
              </span>
              <span className={`roster-status roster-status--${meta.tone}`}>{meta.label}</span>
            </button>
          );
        })}
      </div>

      <button className="nav-item settings">
        <Settings size={15} />
        <span>原型设置</span>
      </button>
    </aside>
  );
}

