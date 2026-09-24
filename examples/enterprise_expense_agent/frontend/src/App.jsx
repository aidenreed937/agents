import React, { useEffect } from 'react';
import { Header } from './components/Header';
import { Navigation } from './components/Navigation';
import { EmployeePortal } from './components/employee/EmployeePortal';
import { HitlCenter } from './components/hitl/HitlCenter';
import { TopologyViewer } from './components/graph/TopologyViewer';
import { useExpenseStore } from './store/useExpenseStore';
import { useHitlStore } from './store/useHitlStore';
import './App.css';

export function App() {
  const activeTab = useExpenseStore((state) => state.activeTab);
  const checkConnection = useExpenseStore((state) => state.checkConnection);
  const isConnected = useExpenseStore((state) => state.isConnected);
  const loadHitlTasks = useHitlStore((state) => state.loadHitlTasks);

  // 初始化健康探测与待办轮询
  useEffect(() => {
    checkConnection();
    loadHitlTasks();

    const timer = setInterval(() => {
      checkConnection();
      if (useExpenseStore.getState().isConnected) {
        useHitlStore.getState().loadHitlTasks();
      }
    }, 6000);

    return () => clearInterval(timer);
  }, [checkConnection, loadHitlTasks]);

  return (
    <div className="app-container">
      <Header />
      <Navigation />
      <main className="main-content">
        {activeTab === 'employee' && <EmployeePortal />}
        {activeTab === 'hitl' && <HitlCenter />}
        {activeTab === 'graph' && <TopologyViewer />}
      </main>
    </div>
  );
}

export default App;
