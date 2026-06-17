import { useDemo } from "../demo/DemoContext";
import { DemoStartMenu } from "../demo/DemoStartMenu";
import { assetUrl } from "../static-demo/assets";

export type Route = "intro" | "network" | "finance" | "office" | "workspace" | "log-demo";

const ITEMS: Array<{ id: Route; label: string }> = [
  { id: "intro", label: "介绍" },
  { id: "network", label: "网络 demo" },
  { id: "finance", label: "财务 demo" },
  { id: "office", label: "3D 办公室" },
  { id: "workspace", label: "工作台" },
  { id: "log-demo", label: "日志演示" },
];

export function TopNav({
  route,
  onNavigate,
}: {
  route: Route;
  onNavigate: (r: Route) => void;
}) {
  const { startDemo, stopDemo } = useDemo();
  const navigateManually = (next: Route) => {
    stopDemo();
    onNavigate(next);
  };
  return (
    <header className="topnav">
      <button className="topnav-brand" onClick={() => navigateManually("intro")}>
        <img className="brand-logo" src={assetUrl("assets/netnomos-forge-logo.png")} alt="" aria-hidden="true" />
        <span className="brand-text">
          <strong>NetNomos Forge</strong>
          <em>规则约束 AI 生成</em>
        </span>
      </button>
      <nav className="topnav-items">
        {ITEMS.map((item) => (
          <button
            key={item.id}
            className={`topnav-item${route === item.id ? " is-active" : ""}`}
            onClick={() => navigateManually(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <DemoStartMenu variant="topnav" onPick={(mode, sub) => startDemo(mode, sub)} />
    </header>
  );
}
