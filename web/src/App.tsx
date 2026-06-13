import { useEffect, useState } from "react";
import { TopNav, type Route } from "./components/TopNav";
import { IntroPage } from "./pages/IntroPage";
import { NetworkDemoPage } from "./pages/NetworkDemoPage";
import { FinanceDemoPage } from "./pages/FinanceDemoPage";

/**
 * 轻量客户端路由：用 hash + 状态切换，不引入 react-router。
 * #/intro · #/network · #/finance · #/office（3D 办公室占位）
 */
function routeFromHash(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  if (h === "network" || h === "finance" || h === "office") return h;
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
    <div className="app-shell">
      <TopNav route={route} onNavigate={navigate} />
      <main className="app-main">
        {route === "intro" && <IntroPage onNavigate={navigate} />}
        {route === "network" && <NetworkDemoPage />}
        {route === "finance" && <FinanceDemoPage />}
        {route === "office" && <OfficePlaceholder onNavigate={navigate} />}
      </main>
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
