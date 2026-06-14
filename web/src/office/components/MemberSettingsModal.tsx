import { AnimatePresence, motion } from "framer-motion";
import { FileText, FolderUp, Network, Paperclip, ShieldCheck, Sliders, X } from "lucide-react";
import { useState } from "react";
import type { Agent } from "../types/domain";
import { CatAvatar } from "./CatAvatar";

interface FConfig {
  files: string[];
  prompt: string;
}

interface MemberSettingsModalProps {
  open: boolean;
  agent: Agent | null;
  rulesLoaded: boolean;
  dataLoaded: boolean;
  fConfig: FConfig;
  onClose: () => void;
  onLoadRules: () => void;
  onLoadData: (filename: string, file?: File) => void;
  onOpenPacket: () => void;
  onAddRagFiles: (list: FileList | null) => void;
  onRemoveRagFile: (name: string) => void;
  onPrompt: (prompt: string) => void;
}

const STATUS_LABEL: Record<string, string> = {
  idle: "待命",
  supervising: "监管中",
  delivering: "配送中",
  analyzing: "分析中",
  validating: "验证中",
  building: "打包中",
  reviewing: "待沟通",
};

export function MemberSettingsModal(props: MemberSettingsModalProps) {
  const { open, agent, onClose } = props;
  return (
    <AnimatePresence>
      {open && agent ? (
        <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.section
            className="rules-modal member-modal"
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.18 }}
          >
            <button className="icon-button modal-close" onClick={onClose} aria-label="关闭">
              <X size={17} />
            </button>
            <div className="member-head">
              <span className="member-avatar">
                <CatAvatar color={agent.color} size={52} radius={14} />
              </span>
              <div>
                <h2>{agent.name}</h2>
                <p>
                  {agent.role} · 状态：{STATUS_LABEL[agent.status] ?? agent.status}
                </p>
              </div>
            </div>

            <div className="member-body">
              <MemberBody {...props} agent={agent} />
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function MemberBody({
  agent,
  rulesLoaded,
  dataLoaded,
  fConfig,
  onLoadRules,
  onLoadData,
  onOpenPacket,
  onAddRagFiles,
  onRemoveRagFile,
  onPrompt,
}: MemberSettingsModalProps & { agent: Agent }) {
  const [enabled, setEnabled] = useState(true);

  if (agent.id === "supervisor") {
    return (
      <>
        <Section icon={<ShieldCheck size={15} />} title="接入规则集">
          <p className="member-note">上传预设规则集文件（YAML / JSON / Markdown），接入后主管 A 进入监管状态。</p>
          <label className="file-drop file-drop--inline">
            <input type="file" multiple onChange={(e) => e.currentTarget.files?.length && onLoadRules()} />
            <FolderUp size={15} />
            <span>选择规则集文件</span>
          </label>
          <div className="member-actions">
            <span className={rulesLoaded ? "badge badge-ok" : "badge"}>{rulesLoaded ? "已接入" : "未接入"}</span>
            <button className="button button-primary" onClick={onLoadRules}>
              使用演示规则集
            </button>
          </div>
        </Section>
        <Section icon={<Sliders size={15} />} title="监管设置">
          <ToggleRow label="Theory 一致性检查" value={enabled} onChange={setEnabled} />
          <p className="member-note">开启后，加载规则集时会校验恒等式之间无冲突，存在冲突的规则会被标灰待人工确认。</p>
        </Section>
      </>
    );
  }

  if (agent.id === "courier") {
    return (
      <>
        <Section icon={<FolderUp size={15} />} title="上传数据">
          <p className="member-note">上传 pcap / csv / xlsx 数据，快递 B 接收后开始往返派送并允许进入抓包工作台。</p>
          <label className="file-drop file-drop--inline">
            <input
              type="file"
              multiple
              onChange={(e) => {
                const f = e.currentTarget.files?.[0];
                if (f) onLoadData(f.name, f);
              }}
            />
            <FolderUp size={15} />
            <span>选择 pcap / csv / xlsx</span>
          </label>
          <div className="member-actions">
            <span className={dataLoaded ? "badge badge-ok" : "badge"}>{dataLoaded ? "数据已加载" : "数据未上传"}</span>
            <button className="button button-primary" onClick={() => onLoadData("demo-pcap-csv-source")}>
              使用演示数据
            </button>
          </div>
        </Section>
        <Section icon={<Network size={15} />} title="抓包工作台">
          <p className="member-note">浏览器端真实解析 pcap / pcapng / csv，逐包查看协议树与 hex。</p>
          <button className="button button-secondary" onClick={onOpenPacket} disabled={!dataLoaded}>
            {dataLoaded ? "进入抓包工作台" : "上传数据后可进入"}
          </button>
        </Section>
      </>
    );
  }

  if (agent.id === "pm") {
    return (
      <>
        <Section icon={<Paperclip size={15} />} title="知识库 RAG 文档">
          <p className="member-note">上传的文档将用于后续接入大模型 + RAG 系统，让 F 基于这些资料做受约束回答。</p>
          <label className="file-drop file-drop--inline">
            <input type="file" multiple onChange={(e) => onAddRagFiles(e.currentTarget.files)} />
            <Paperclip size={15} />
            <span>上传 PDF / Markdown / TXT</span>
          </label>
          {fConfig.files.length ? (
            <ul className="member-files">
              {fConfig.files.map((f) => (
                <li key={f}>
                  <FileText size={13} />
                  <span>{f}</span>
                  <button onClick={() => onRemoveRagFile(f)} aria-label="移除">
                    <X size={12} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="member-empty">尚未上传文档</p>
          )}
        </Section>
        <Section icon={<Sliders size={15} />} title="System Prompt / 角色设定">
          <textarea
            className="member-prompt"
            value={fConfig.prompt}
            onChange={(e) => onPrompt(e.target.value)}
            rows={4}
            placeholder="设定 F 的回答风格与约束…"
          />
        </Section>
      </>
    );
  }

  // 员工 C / D / E：通用角色设置
  return (
    <>
      <Section icon={<Sliders size={15} />} title="角色说明">
        <p className="member-note">{agent.description}</p>
      </Section>
      <Section icon={<Sliders size={15} />} title="设置">
        <ToggleRow label="参与流水线" value={enabled} onChange={setEnabled} />
        <p className="member-note">更多参数（模型、阈值、采样等）将在接入后端后开放，当前为前端演示占位。</p>
      </Section>
    </>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section className="member-section">
      <p className="member-section-title">
        {icon}
        {title}
      </p>
      {children}
    </section>
  );
}

function ToggleRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="member-toggle-row">
      <span>{label}</span>
      <button className={`rule-toggle ${value ? "is-on" : ""}`} onClick={() => onChange(!value)} aria-label={label}>
        <span />
      </button>
    </div>
  );
}
