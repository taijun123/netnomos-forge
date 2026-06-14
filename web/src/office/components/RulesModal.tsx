import { AnimatePresence, motion } from "framer-motion";
import { FolderPlus, Plus, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import type { RuleGroup } from "../types/domain";

const RULE_TYPES = ["约束", "恒等式", "范围", "蕴含", "比率", "自定义"];
const DOMAINS = ["财务", "网络", "工业", "医疗", "通用"];

interface RulesModalProps {
  open: boolean;
  groups: RuleGroup[];
  onClose: () => void;
  onToggle: (groupId: string, ruleId: string) => void;
  onAddRule: (groupId: string, text: string, type: string) => void;
  onAddGroup: (name: string, domain: string) => void;
}

export function RulesModal({ open, groups, onClose, onToggle, onAddRule, onAddGroup }: RulesModalProps) {
  const [groupName, setGroupName] = useState("");
  const [groupDomain, setGroupDomain] = useState(DOMAINS[0]);

  const totalRules = groups.reduce((n, g) => n + g.rules.length, 0);
  const enabledRules = groups.reduce((n, g) => n + g.rules.filter((r) => r.enabled).length, 0);

  function submitGroup() {
    const n = groupName.trim();
    if (!n) return;
    onAddGroup(n, groupDomain);
    setGroupName("");
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.section
            className="rules-modal"
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.18 }}
          >
            <button className="icon-button modal-close" onClick={onClose} aria-label="关闭">
              <X size={17} />
            </button>
            <div className="rules-modal-head">
              <div className="modal-icon">
                <ShieldCheck size={22} />
              </div>
              <div>
                <h2>规则集</h2>
                <p>
                  按规则组管理约束。共 {groups.length} 组 / {totalRules} 条，已启用 {enabledRules} 条。
                </p>
              </div>
            </div>

            <div className="rules-list">
              {groups.map((group) => (
                <RuleGroupCard key={group.id} group={group} onToggle={onToggle} onAddRule={onAddRule} />
              ))}
            </div>

            <div className="rules-create">
              <p className="rules-create-title">
                <FolderPlus size={14} /> 新建规则组
              </p>
              <div className="rules-create-row">
                <input
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submitGroup();
                  }}
                  placeholder="组名称，如：工业质检规则组"
                />
                <select value={groupDomain} onChange={(e) => setGroupDomain(e.target.value)}>
                  {DOMAINS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
                <button className="button button-primary" onClick={submitGroup}>
                  建组
                </button>
              </div>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function RuleGroupCard({
  group,
  onToggle,
  onAddRule,
}: {
  group: RuleGroup;
  onToggle: (groupId: string, ruleId: string) => void;
  onAddRule: (groupId: string, text: string, type: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const [text, setText] = useState("");
  const [type, setType] = useState(RULE_TYPES[0]);
  const enabled = group.rules.filter((r) => r.enabled).length;

  function submit() {
    const t = text.trim();
    if (!t) return;
    onAddRule(group.id, t, type);
    setText("");
  }

  return (
    <div className="rule-group">
      <button className="rule-group-head" onClick={() => setOpen((v) => !v)}>
        <span className={`rule-group-caret ${open ? "is-open" : ""}`}>▸</span>
        <strong>{group.name}</strong>
        {group.discovered ? <em className="rule-group-disc">自发现</em> : <em className="rule-group-domain">{group.domain}</em>}
        <span className="rule-group-count">
          {enabled}/{group.rules.length}
        </span>
      </button>

      {open ? (
        <div className="rule-group-body">
          {group.discovered ? (
            <p className="rule-disc-hint">
              员工D 从「{group.from}」自发现的候选规则，勾选开关即纳入规则集；疑似巧合项默认关闭，请人工确认。
            </p>
          ) : null}
          {group.rules.map((rule) => (
            <div key={rule.id} className={`rule-row ${rule.enabled ? "" : "is-off"}`}>
              <span className="rule-id">{rule.id}</span>
              <div className="rule-main">
                <strong>{rule.text}</strong>
                <span className="rule-tags">
                  <em className="rule-type">{rule.type}</em>
                  <em className={`rule-src rule-src--${rule.source}`}>
                    {rule.source === "preset" ? "预置" : rule.source === "learned" ? "自发现" : "自建"}
                  </em>
                  {typeof rule.confidence === "number" ? <em className="rule-conf">置信 {rule.confidence.toFixed(2)}</em> : null}
                  {rule.coincidence ? <em className="rule-coin">疑似巧合</em> : null}
                </span>
              </div>
              <button
                className={`rule-toggle ${rule.enabled ? "is-on" : ""}`}
                onClick={() => onToggle(group.id, rule.id)}
                aria-label={rule.enabled ? "停用" : "启用"}
              >
                <span />
              </button>
            </div>
          ))}

          <div className="rule-add-row">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
              placeholder={`向「${group.name}」添加规则…`}
            />
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {RULE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <button className="rule-add-btn" onClick={submit} aria-label="添加规则">
              <Plus size={15} />
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
