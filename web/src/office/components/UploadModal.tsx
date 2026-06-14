import { AnimatePresence, motion } from "framer-motion";
import { FolderUp, ShieldCheck, X } from "lucide-react";

interface UploadModalProps {
  kind: "rules" | "data";
  open: boolean;
  onClose: () => void;
  onConfirm: (label: string) => void;
}

export function UploadModal({ kind, open, onClose, onConfirm }: UploadModalProps) {
  const isRules = kind === "rules";
  const title = isRules ? "上传预设规则集" : "上传数据目录";
  const description = isRules
    ? "演示上传 YAML / JSON / Markdown 规则文件，主管A随后进入监管状态。"
    : "演示选择 pcap/csv 数据目录，快递B随后开始反复派送数据并允许进入抓包工作台。";

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.section
            className="upload-modal"
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.18 }}
          >
            <button className="icon-button modal-close" onClick={onClose} aria-label="关闭">
              <X size={17} />
            </button>
            <div className="modal-icon">{isRules ? <ShieldCheck size={26} /> : <FolderUp size={26} />}</div>
            <h2>{title}</h2>
            <p>{description}</p>
            <label className="file-drop">
              <input
                type="file"
                multiple
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  onConfirm(file?.name ?? (isRules ? "preset-rules.yaml" : "traffic-source.pcap/csv"));
                }}
              />
              <span>{isRules ? "选择规则文件" : "选择 pcap / csv 示例文件"}</span>
              <small>这里仅做 UI 演示，不读取文件内容。</small>
            </label>
            <div className="modal-actions">
              <button className="button button-secondary" onClick={onClose}>
                取消
              </button>
              <button
                className="button button-primary"
                onClick={() =>
                  onConfirm(isRules ? "preset-rules.yaml" : "demo-pcap-csv-source")
                }
              >
                使用演示数据
              </button>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
