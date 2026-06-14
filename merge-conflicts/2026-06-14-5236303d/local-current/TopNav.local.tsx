import { Shield } from "lucide-react";
import { useDemo } from "../demo/DemoContext";
import { DemoStartMenu } from "../demo/DemoStartMenu";

export type Route = "intro" | "network" | "finance" | "office" | "workspace" | "log-demo";

const ITEMS: Array<{ id: Route; label: string }> = [
  { id: "intro", label: "产品定义" },
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
  const { startDemo } = useDemo();
  return (
    <header className="topnav">
      <button className="topnav-brand" onClick={() => onNavigate("intro")} type="button">
        <span className="brand-mark" aria-hidden>
          <Shield size={15} strokeWidth={2.1} />
        </span>
        <span className="brand-text">
          <strong>NetNomos Forge</strong>
          <em>规则强约束层</em>
        </span>
      </button>
      <nav className="topnav-items" aria-label="主导航">
        {ITEMS.map((item) => (
          <button
            key={item.id}
            className={`topnav-item${route === item.id ? " is-active" : ""}`}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </nav>
      <DemoStartMenu variant="topnav" onPick={(mode, sub) => startDemo(mode, sub)} />
    </header>
  );
}
