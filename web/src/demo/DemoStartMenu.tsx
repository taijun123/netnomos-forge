// 「开始演示」悬停选择浮层。顶栏与办公室入口共用：hover 展开 演示网络/演示财务（顶栏另含 3D 办公室）。
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import type { DemoScenario } from "./demoAssets";

type Mode = "network" | "finance" | "office";

export function DemoStartMenu({
  variant,
  onPick,
  includeOffice = true,
}: {
  variant: "topnav" | "office";
  onPick: (mode: Mode, sub?: DemoScenario) => void;
  includeOffice?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const pickNetwork = () => (variant === "office" ? onPick("office", "network") : onPick("network"));
  const pickFinance = () => (variant === "office" ? onPick("office", "finance") : onPick("finance"));

  return (
    <div
      className={`demo-start demo-start--${variant}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button type="button" className="demo-start-trigger topnav-cta" onClick={pickNetwork}>
        ▶ 一键演示
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            className="demo-start-menu"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.14 }}
          >
            <span className="demo-start-menu-title">选择演示场景</span>
            <button type="button" onClick={pickNetwork}>
              <strong>网络流量</strong>
              <em>NetFlow 规则自发现 → 核查 → 双轨</em>
            </button>
            <button type="button" onClick={pickFinance}>
              <strong>财务报表</strong>
              <em>勾稽规则 → 核查 → 修正双轨</em>
            </button>
            {variant === "topnav" && includeOffice && (
              <button type="button" onClick={() => onPick("office", "network")}>
                <strong>3D 办公室</strong>
                <em>多智能体演绎 · 手机群聊看结果</em>
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
