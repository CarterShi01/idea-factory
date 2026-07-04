export type Tab = "overview" | "ideas" | "decisions" | "signals" | "run" | "profile";

const ITEMS: { key: Tab; label: string; ico: string }[] = [
  { key: "overview", label: "概览", ico: "◉" },
  { key: "ideas", label: "创意", ico: "✦" },
  { key: "decisions", label: "评估决策", ico: "⊘" },
  { key: "signals", label: "信号", ico: "≈" },
  { key: "run", label: "运行管线", ico: "▷" },
  { key: "profile", label: "画像", ico: "☰" },
];

export function Sidebar({
  tab,
  onTab,
  onLogout,
}: {
  tab: Tab;
  onTab: (t: Tab) => void;
  onLogout: () => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="logo">创</div>
        <div className="name">
          创意工厂
          <small>控制台</small>
        </div>
      </div>
      <nav className="nav">
        {ITEMS.map((it) => (
          <button key={it.key} className={tab === it.key ? "active" : ""} onClick={() => onTab(it.key)}>
            <span className="ico">{it.ico}</span>
            {it.label}
          </button>
        ))}
      </nav>
      <div className="foot">
        <button className="nav" style={{ all: "unset", cursor: "pointer", color: "inherit" }} onClick={onLogout}>
          退出登录
        </button>
        <div style={{ marginTop: 8 }}>v0.1 · 三源创意引擎</div>
      </div>
    </aside>
  );
}
