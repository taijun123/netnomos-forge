import { useEffect, useState } from "react";
import { TopNav, type Route } from "./components/TopNav";
import { IntroPage } from "./pages/IntroPage";
import { NetworkDemoPage } from "./pages/NetworkDemoPage";
import { FinanceDemoPage } from "./pages/FinanceDemoPage";
import { OfficeDemoPage } from "./pages/OfficeDemoPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { DemoProvider } from "./demo/DemoContext";

/**
 * 轻量客户端路由：用 hash + 状态切换，不引入 react-router。
 * #/intro · #/network · #/finance · #/office · #/workspace
 */
function routeFromHash(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  if (h === "network" || h === "finance" || h === "office" || h === "workspace") {
    return h;
  }
  return "intro";
}

export function App() {
  const [route, setRoute] = useState<Route>(() => routeFromHash());

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
        </main>
      </div>
    </DemoProvider>
  );
}
