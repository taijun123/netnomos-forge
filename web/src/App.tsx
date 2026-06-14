import { useEffect, useState } from "react";
import { TopNav, type Route } from "./components/TopNav";
import { IntroPage } from "./pages/IntroPage";
import { NetworkDemoPage } from "./pages/NetworkDemoPage";
import { FinanceDemoPage } from "./pages/FinanceDemoPage";
import { OfficeDemoPage } from "./pages/OfficeDemoPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { LogDemoPage } from "./pages/LogDemoPage";
import { LogPanel } from "./components/LogPanel";
import { DemoProvider } from "./demo/DemoContext";

/**
 * 轻量客户端路由：用 hash + 状态切换，不引入 react-router。
 * #/intro · #/network · #/finance · #/office · #/workspace · #/log-demo
 */
function routeFromHash(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  if (h === "network" || h === "finance" || h === "office" || h === "workspace" || h === "log-demo") {
    return h;
  }
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
    <DemoProvider navigate={navigate}>
      <div className="app-shell">
        <TopNav route={route} onNavigate={navigate} />
        <main className="app-main">
          {route === "intro" && <IntroPage onNavigate={navigate} />}
          {route === "network" && <NetworkDemoPage />}
          {route === "finance" && <FinanceDemoPage />}
          {route === "office" && <OfficeDemoPage />}
          {route === "workspace" && <WorkspacePage />}
          {route === "log-demo" && <LogDemoPage />}
        </main>

        {(route === "log-demo" || showLogPanel) && (
          <button
            type="button"
            onClick={() => setShowLogPanel(!showLogPanel)}
            className="log-panel-toggle"
            title="切换日志面板"
          >
            {showLogPanel ? "隐藏日志" : "显示日志"}
          </button>
        )}

        {showLogPanel && (
          <div className="log-panel-dock">
            <LogPanel />
          </div>
        )}
      </div>
    </DemoProvider>
  );
}
