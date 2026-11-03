import { useEffect, useState } from "react";

import { Review } from "./Review";
import { TodayScreen } from "./Today";

function currentPath() {
  return window.location.pathname;
}

export function navigate(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function App() {
  const [path, setPath] = useState(currentPath());
  useEffect(() => {
    const onPop = () => setPath(currentPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const claimId = path.match(/^\/claims\/([\w-]+)/)?.[1];

  return (
    <div className="shell">
      <nav className="sidebar" aria-label="Main">
        <a className="logo" href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }}>lipwad</a>
        <a href="/" aria-current={!claimId ? "page" : undefined} onClick={(e) => { e.preventDefault(); navigate("/"); }}>Today</a>
        <a href="/" aria-current={claimId ? "page" : undefined} onClick={(e) => { e.preventDefault(); navigate("/"); }}>Claims</a>
        <span className="nav-muted">Money</span>
        <span className="nav-muted">SHA rules</span>
        <div className="facility">
          <strong>Upendo County Hospital</strong>
          <span>Level 4 · demo data</span>
        </div>
      </nav>
      <main className="content">{claimId ? <Review claimId={claimId} /> : <TodayScreen />}</main>
      <nav className="tabbar" aria-label="Main">
        <a href="/" aria-current={!claimId ? "page" : undefined} onClick={(e) => { e.preventDefault(); navigate("/"); }}>Today</a>
        <a href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }}>Claims</a>
      </nav>
    </div>
  );
}
