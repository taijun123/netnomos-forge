import React, { useEffect, useState } from "react";
import { TopNav, type Route } from "./components/TopNav";
import { IntroPage } from "./pages/IntroPage";
import { NetworkDemoPage } from "./pages/NetworkDemoPage";
import { FinanceDemoPage } from "./pages/FinanceDemoPage";
import { LogDemoPage } from "./pages/LogDemoPage";
import { LogPanel } from "./components/LogPanel";

/**
 * 轻量客户端路由：用 hash + 状态切换，不引入 react-router。
 * #/intro · #/network · #/finance · #/office · #/log-demo（日志演示页面）
 */
function routeFromHash(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  if (h === "network" || h === "finance" || h === "office" || h === "log-demo") return h;
  return "intro";
}

export function App() {
  const [route, setRoute] = useState<Route>(() => routeFromHash());
  const [showLogPanel, setShowLogPanel] = useState(false);

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (next: Route) => {
    window.location.hash = `#/${next}`;
    setRoute(next);
    // 切页回到顶部
    const main = document.querySelector(".app-main");
    main?.scrollTo({ top: 0 });
  };

  return (
    <div className="app-shell">
      <TopNav route={route} onNavigate={navigate} />
      <main className="app-main">
        {route === "intro" && <IntroPage onNavigate={navigate} />}
        {route === "network" && <NetworkDemoPage />}
        {route === "finance" && <FinanceDemoPage />}
        {route === "office" && <OfficePlaceholder onNavigate={navigate} />}
        {route === "log-demo" && <LogDemoPage />}
      </main>

      {/* 日志面板切换按钮 */}
      <button
        onClick={() => setShowLogPanel(!showLogPanel)}
        className="fixed bottom-4 right-4 bg-blue-500 text-white px-4 py-2 rounded-full shadow-lg hover:bg-blue-600 active:bg-blue-700 transition z-[9999] pointer-events-auto cursor-pointer"
        title="切换日志面板"
        style={{ pointerEvents: 'auto', cursor: 'pointer' }}
      >
        {showLogPanel ? '📋 隐藏日志' : '📋 显示日志'}
      </button>

      {/* 日志面板 */}
      {showLogPanel && (
        <div className="fixed bottom-16 right-4 w-96 max-h-[500px] shadow-2xl z-40">
          <LogPanel />
        </div>
      )}
    </div>
  );
}

function OfficePlaceholder({ onNavigate }: { onNavigate: (r: Route) => void }) {
  return (
    <div className="page-pad office-placeholder">
      <div className="placeholder-card glass">
        <span className="placeholder-badge">即将上线</span>
        <h1>3D 多 Agent 办公室</h1>
        <p>
          趣味演示界面（marvis product），与产品页消费同一条 SSE 工作流事件流：主管 A
          / 快递 B / 员工 C–E / 经理 F 在 3D 办公室里实时联动。第五周接入，当前为占位入口。
        </p>
        <button className="btn btn-primary" onClick={() => onNavigate("intro")}>
          返回介绍页
        </button>
      </div>
    </div>
  );
}
