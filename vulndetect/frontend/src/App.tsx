import { DashboardLayout } from './layouts/DashboardLayout';
import { Dashboard } from './pages/Dashboard';
import { TrainingMonitor } from './pages/TrainingMonitor';
import { EvalReport } from './pages/EvalReport';
import { DataManager } from './pages/DataManager';
import { Playground } from './pages/Playground';

function getPage() {
  const path = window.location.pathname;
  switch (path) {
    case '/training': return <TrainingMonitor />;
    case '/evaluation': return <EvalReport />;
    case '/data': return <DataManager />;
    case '/playground': return <Playground />;
    default: return <Dashboard />;
  }
}

export default function App() {
  return <DashboardLayout>{getPage()}</DashboardLayout>;
}
