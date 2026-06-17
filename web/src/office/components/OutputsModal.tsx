import { AnimatePresence, motion } from "framer-motion";
import { Boxes, FileText, X } from "lucide-react";
import { useState } from "react";
import { MarkdownBlock } from "../../components/MarkdownBlock";
import { agentNameMap } from "../data/mockData";
import type { Artifact } from "../types/domain";

interface OutputsModalProps {
  open: boolean;
  artifacts: Artifact[];
  onClose: () => void;
}

export function OutputsModal({ open, artifacts, onClose }: OutputsModalProps) {
  const [viewing, setViewing] = useState<Artifact | null>(null);

  // 按产出员工分组
  const byProducer = new Map<string, Artifact[]>();
  for (const a of artifacts) {
    const list = byProducer.get(a.producer) ?? [];
    list.push(a);
    byProducer.set(a.producer, list);
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
            <button
              className="icon-button modal-close"
              onClick={() => (viewing ? setViewing(null) : onClose())}
              aria-label="关闭"
            >
              <X size={17} />
            </button>
            <div className="rules-modal-head">
              <div className="modal-icon">
                <Boxes size={22} />
              </div>
              <div>
                <h2>{viewing ? viewing.title : "产出物"}</h2>
                <p>
                  {viewing
                    ? `${agentNameMap[viewing.producer] ?? viewing.producer} · ${viewing.kind} · ${viewing.time}`
                    : `各员工产出的文档与制品，共 ${artifacts.length} 项。`}
                </p>
              </div>
            </div>

            {viewing ? (
              <div className="rules-list">
                <div className="artifact-doc">
                  <MarkdownBlock text={viewing.preview} />
                </div>
                <button className="rules-card-more" onClick={() => setViewing(null)}>
                  ‹ 返回产出物列表
                </button>
              </div>
            ) : (
              <div className="rules-list">
                {[...byProducer.entries()].map(([producer, list]) => (
                  <div key={producer} className="output-group">
                    <p className="output-producer">{agentNameMap[producer] ?? producer}</p>
                    {list.map((a) => (
                      <button key={a.id} className="output-row" onClick={() => setViewing(a)}>
                        <span className="output-icon">
                          <FileText size={16} />
                        </span>
                        <div className="output-main">
                          <strong>{a.title}</strong>
                          <small>
                            {a.kind} · {a.time}
                          </small>
                        </div>
                        <span className="output-view">查看 ›</span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
