import { useEffect, useState } from "react";

import { ClaimsScreen } from "./Claims";
import { MoneyScreen } from "./Money";
import { Review } from "./Review";
import { RulesScreen } from "./Rules";
import { TodayScreen } from "./Today";
import { Link, NavIcon } from "./ui";

function currentPath() {
  return window.location.pathname.replace(/(.)\/+$/, "$1");
}

const SECTIONS = [
  { to: "/", label: "Today" },
  { to: "/claims", label: "Claims" },
  { to: "/money", label: "Money" },
  { to: "/rules", label: "SHA rules" },
];

const COLLAPSED_KEY = "lipwad.sidebar.collapsed";

/** The viewer's own choice, or collapsed by default on screens narrower than 1024px. */
function initialCollapsed(): boolean {
  try {
    const saved = window.localStorage.getItem(COLLAPSED_KEY);
    if (saved !== null) return saved === "1";
  } catch {
    // storage can be unavailable; fall back to the screen width
  }
  return window.innerWidth < 1024;
}

export function App() {
  const [path, setPath] = useState(currentPath());
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  function toggle() {
    setCollapsed((was) => {
      try { window.localStorage.setItem(COLLAPSED_KEY, was ? "0" : "1"); } catch { /* not saved */ }
      return !was;
    });
  }
  useEffect(() => {
    // Ctrl+B (Cmd+B on a Mac) toggles the sidebar, except while typing.
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "b" || e.altKey || e.shiftKey || !(IS_MAC ? e.metaKey : e.ctrlKey)) return;
      const target = e.target as HTMLElement | null;
      if (target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))) return;
      e.preventDefault();
      toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    const onPop = () => setPath(currentPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const claimId = path.match(/^\/claims\/([\w-]+)/)?.[1];
  const section = claimId ? "/claims" : SECTIONS.find((s) => s.to === path)?.to ?? "/";
  const screen = claimId ? <Review key={claimId} claimId={claimId} />
    : section === "/claims" ? <ClaimsScreen />
    : section === "/money" ? <MoneyScreen />
    : section === "/rules" ? <RulesScreen />
    : <TodayScreen />;
  const links = SECTIONS.map((s) => (
    <Link key={s.to} to={s.to} current={s.to === section} className="nav-link" tip={collapsed ? s.label : undefined}>
      <NavIcon to={s.to} />
      <span className="nav-label">{s.label}</span>
    </Link>
  ));
  const action = collapsed ? "Expand sidebar" : "Collapse sidebar";

  return (
    <div className={collapsed ? "shell collapsed" : "shell"}>
      <nav className="sidebar" aria-label="Main" id="main-nav">
        <div className="sidebar-top">
          {!collapsed && <Link to="/" className="logo">lipwad</Link>}
          <button
            className="sidebar-toggle"
            onClick={toggle}
            aria-expanded={!collapsed}
            aria-controls="main-nav"
            aria-label={action}
            data-tip={`${action} (${SHORTCUT})`}
          >
            <PanelIcon open={collapsed} />
          </button>
        </div>
        {links}
        <div className="facility">
          <strong className="nav-label">Upendo County Hospital</strong>
        </div>
      </nav>
      <main className="content">{screen}</main>
    </div>
  );
}

const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const SHORTCUT = IS_MAC ? "⌘B" : "Ctrl+B";

/** Lucide's PanelLeftOpen and PanelLeftClose icons (ISC licence), inlined. */
function PanelIcon({ open }: { open: boolean }) {
  return (
    <svg className="panel-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="18" height="18" x="3" y="3" rx="2" />
      <path d="M9 3v18" />
      <path d={open ? "m14 9 3 3-3 3" : "m16 15-3-3 3-3"} />
    </svg>
  );
}
