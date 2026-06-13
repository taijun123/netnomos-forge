export type Route = "intro" | "network" | "finance" | "office";

const ITEMS: Array<{ id: Route; label: string }> = [
  { id: "intro", label: "介绍" },
  { id: "network", label: "网络 demo" },
  { id: "finance", label: "财务 demo" },
  { id: "office", label: "3D 办公室" },
];

export function TopNav({
  route,
  onNavigate,
}: {
  route: Route;
  onNavigate: (r: Route) => void;
}) {
  return (
    <header className="topnav">
      <button className="topnav-brand" onClick={() => onNavigate("intro")}>
        <span className="brand-mark" aria-hidden>
          NN
        </span>
        <span className="brand-text">
          <strong>NetNomos Forge</strong>
          <em>不改模型，只加规则</em>
        </span>
      </button>
      <nav className="topnav-items">
        {ITEMS.map((item) => (
          <button
            key={item.id}
            className={`topnav-item${route === item.id ? " is-active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            {item.label}
            {item.id === "office" && <i className="topnav-soon">soon</i>}
          </button>
        ))}
      </nav>
      <a
        className="topnav-cta"
        href="#/network"
        onClick={(e) => {
          e.preventDefault();
          onNavigate("network");
        }}
      >
        开始演示
      </a>
    </header>
  );
}
