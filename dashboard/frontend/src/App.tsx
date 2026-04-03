import { useEffect, useState } from "react";
import { Dashboard } from "./components/mockups/ironpass/Dashboard";
import { AuditLog } from "./components/mockups/ironpass/AuditLog";
import { Violations } from "./components/mockups/ironpass/Violations";
import { Agents } from "./components/mockups/ironpass/Agents";
import { Frameworks } from "./components/mockups/ironpass/Frameworks";
import { Policies } from "./components/mockups/ironpass/Policies";
import { Guardrails } from "./components/mockups/ironpass/Guardrails";
import { Governance } from "./components/mockups/ironpass/Governance";
import { TestConsole } from "./components/mockups/ironpass/TestConsole";
import { Reports } from "./components/mockups/ironpass/Reports";
import { ApiKeys } from "./components/mockups/ironpass/ApiKeys";
import { Team } from "./components/mockups/ironpass/Team";
import { Settings } from "./components/mockups/ironpass/Settings";
import { Login } from "./components/mockups/ironpass/Login";

function App() {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || "login");

  useEffect(() => {
    const handleHashChange = () => setRoute(window.location.hash.slice(1) || "login");
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  switch (route) {
    case "login": return <Login />;
    case "dashboard": return <Dashboard />;
    case "audit": return <AuditLog />;
    case "violations": return <Violations />;
    case "agents": return <Agents />;
    case "frameworks": return <Frameworks />;
    case "policies": return <Policies />;
    case "guardrails": return <Guardrails />;
    case "governance": return <Governance />;
    case "console": return <TestConsole />;
    case "reports": return <Reports />;
    case "api-keys": return <ApiKeys />;
    case "team": return <Team />;
    case "settings": return <Settings />;
    default: return <Login />;
  }
}

export default App;
