import { useEffect, useState } from "react";
import { AMLPage } from "./pages/AMLPage";
import { Dashboard } from "./components/mockups/covenant/Dashboard";
import { AuditLog } from "./components/mockups/covenant/AuditLog";
import { Violations } from "./components/mockups/covenant/Violations";
import { Agents } from "./components/mockups/covenant/Agents";
import { Frameworks } from "./components/mockups/covenant/Frameworks";
import { Policies } from "./components/mockups/covenant/Policies";
import { Guardrails } from "./components/mockups/covenant/Guardrails";
import { Governance } from "./components/mockups/covenant/Governance";
import { TestConsole } from "./components/mockups/covenant/TestConsole";
import { Reports } from "./components/mockups/covenant/Reports";
import { ApiKeys } from "./components/mockups/covenant/ApiKeys";
import { Team } from "./components/mockups/covenant/Team";
import { Settings } from "./components/mockups/covenant/Settings";
import { Login } from "./components/mockups/covenant/Login";
import { Workspaces } from "./components/mockups/covenant/Workspaces";
import { ComplianceLayer } from "./components/mockups/covenant/ComplianceLayer";
import { AgentSecuritySuite } from "./components/mockups/covenant/AgentSecuritySuite";
import { Legal } from "./components/mockups/covenant/Legal";
import { GovAnalytics } from "./components/mockups/covenant/GovAnalytics";
import { FunctionsAndTools } from "./components/mockups/covenant/FunctionsAndTools";
import { IndustrySuites } from "./components/mockups/covenant/IndustrySuites";

function App() {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || "login");

  useEffect(() => {
    const handleHashChange = () => setRoute(window.location.hash.slice(1) || "login");
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  switch (route) {
    case "login": return <Login />;
    case "workspaces": return <Workspaces />;
    case "compliance-layer": return <ComplianceLayer />;
    case "operations-functions": return <OperationsFunctions />;
    case "agent-security-suite": return <AgentSecuritySuite />;
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
    case "aml": return <AMLPage />;
    case "legal": return <Legal />;
    case "gov-analytics": return <GovAnalytics />;
    case "functions-tools": return <FunctionsAndTools />;
    case "industry-suites": return <IndustrySuites />;
    default: return <Login />;
  }
}

export default App;
