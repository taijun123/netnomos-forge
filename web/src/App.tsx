import { useEffect, useState } from "react";
import { TopNav, type Route } from "./components/TopNav";
import { IntroPage } from "./pages/IntroPage";
import { NetworkDemoPage } from "./pages/NetworkDemoPage";
import { FinanceDemoPage } from "./pages/FinanceDemoPage";
import { OfficeDemoPage } from "./pages/OfficeDemoPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { LogDemoPage } from "./pages/LogDemoPage";
import { DemoProvider } from "./demo/DemoContext";
import { LogPanel } from "./components/LogPanel";

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
  const showLogControls = route === "log-demo" || showLogPanel;

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    setShowLogPanel(route === "log-demo");
    window.scrollTo({ top: 0, left: 0 });
  }, [route]);

  const navigate = (next: Route) => {
    window.location.hash = `#/${next}`;
    setRoute(next);
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
        {showLogControls && (
          <button
            className="log-panel-toggle"
            type="button"
            onClick={() => setShowLogPanel((value) => !value)}
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
