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

export function App() {
  const [path, setPath] = useState(currentPath());
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
    <Link key={s.to} to={s.to} current={s.to === section} className="nav-link">
      <NavIcon to={s.to} />
      <span className="nav-label">{s.label}</span>
    </Link>
  ));

  return (
    <div className="shell">
      <nav className="sidebar" aria-label="Main">
        <Link to="/" className="logo"><span className="logo-full">lipwad</span><span className="logo-short" aria-hidden="true">L</span></Link>
        {links}
        <div className="facility">
          <strong className="nav-label">Upendo County Hospital</strong>
          <span className="sidebar-badge" title="Synthetic data, demo only">
            <span aria-hidden="true">◆</span>
            <span className="nav-label">Synthetic data, demo only</span>
          </span>
        </div>
      </nav>
      <main className="content">{screen}</main>
    </div>
  );
}
