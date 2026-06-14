import { useEffect, useState } from "react";
import { TopNav, type Route } from "./components/TopNav";
import { IntroPage } from "./pages/IntroPage";
import { NetworkDemoPage } from "./pages/NetworkDemoPage";
import { FinanceDemoPage } from "./pages/FinanceDemoPage";
import { OfficeDemoPage } from "./pages/OfficeDemoPage";
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
          {route === "workspace" && <OfficeDemoPage />}
          {route === "log-demo" && <LogDemoPage />}
        </main>

        <button
          type="button"
          onClick={() => setShowLogPanel(!showLogPanel)}
          className="fixed bottom-4 right-4 bg-blue-500 text-white px-4 py-2 rounded-full shadow-lg hover:bg-blue-600 transition z-50"
          title="切换日志面板"
        >
          {showLogPanel ? "📋 隐藏日志" : "📋 显示日志"}
        </button>

        {showLogPanel && (
          <div className="fixed bottom-16 right-4 w-96 max-h-[500px] shadow-2xl z-40">
            <LogPanel />
          </div>
        )}
      </div>
    </DemoProvider>
  );
}
