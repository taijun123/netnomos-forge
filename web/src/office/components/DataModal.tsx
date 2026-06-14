import { AnimatePresence, motion } from "framer-motion";
import { Database, FileSpreadsheet, FileText, Network, X } from "lucide-react";
import type { DataSource } from "../types/domain";

interface DataModalProps {
  open: boolean;
  sources: DataSource[];
  onClose: () => void;
}

const KIND_ICON = {
  pcap: Network,
  csv: FileText,
  xlsx: FileSpreadsheet,
  pdf: FileText,
} as const;

export function DataModal({ open, sources, onClose }: DataModalProps) {
  const loaded = sources.filter((s) => s.status === "已加载").length;
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
                <Database size={22} />
              </div>
              <div>
                <h2>数据</h2>
                <p>
                  已上传 / 加载的数据源，共 {sources.length} 个，已加载 {loaded} 个。
                </p>
              </div>
            </div>

            <div className="rules-list">
              {sources.map((s) => {
                const Icon = KIND_ICON[s.kind] ?? FileText;
                return (
                  <div key={s.id} className="data-row">
                    <span className={`data-icon data-icon--${s.kind}`}>
                      <Icon size={18} />
                    </span>
                    <div className="data-main">
                      <strong>{s.name}</strong>
                      <small>{s.meta}</small>
                    </div>
                    <div className="data-tags">
                      <em className={`data-status data-status--${s.status === "已加载" ? "on" : "wait"}`}>{s.status}</em>
                      <em className={`rule-src rule-src--${s.source === "preset" ? "preset" : "custom"}`}>
                        {s.source === "preset" ? "预置" : "上传"}
                      </em>
                    </div>
                  </div>
                );
              })}
              {sources.length === 0 ? <p className="data-empty">暂无数据，去快递B的设置里上传 pcap / csv / xlsx。</p> : null}
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
