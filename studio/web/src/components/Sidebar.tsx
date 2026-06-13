export type Tab = "overview" | "ideas" | "decisions" | "signals" | "run";

const ITEMS: { key: Tab; label: string; ico: string }[] = [
  { key: "overview", label: "Overview", ico: "◉" },
  { key: "ideas", label: "Ideas", ico: "✦" },
  { key: "decisions", label: "Decisions", ico: "⊘" },
  { key: "signals", label: "Signals", ico: "≈" },
  { key: "run", label: "Run pipeline", ico: "▷" },
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
        <div className="logo">IF</div>
        <div className="name">
          Idea Factory
          <small>STUDIO</small>
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
          Sign out
        </button>
        <div style={{ marginTop: 8 }}>v0.1 · 3-source idea engine</div>
      </div>
    </aside>
  );
}
