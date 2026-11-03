import { useEffect, useState } from "react";

import { ClaimsScreen } from "./Claims";
import { MoneyScreen } from "./Money";
import { Review } from "./Review";
import { RulesScreen } from "./Rules";
import { TodayScreen } from "./Today";
import { Link } from "./ui";

function currentPath() {
  return window.location.pathname;
}

export function navigate(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo(0, 0);
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
  const screen = claimId ? <Review claimId={claimId} />
    : section === "/claims" ? <ClaimsScreen />
    : section === "/money" ? <MoneyScreen />
    : section === "/rules" ? <RulesScreen />
    : <TodayScreen />;
  const links = SECTIONS.map((s) => <Link key={s.to} to={s.to} current={s.to === section}>{s.label}</Link>);

  return (
    <div className="shell">
      <nav className="sidebar" aria-label="Main">
        <Link to="/" className="logo">lipwad</Link>
        {links}
        <div className="facility">
          <strong>Upendo County Hospital</strong>
          <span>Level 4 · demo data</span>
        </div>
      </nav>
      <main className="content">{screen}</main>
      <nav className="tabbar" aria-label="Main">{links}</nav>
    </div>
  );
}
