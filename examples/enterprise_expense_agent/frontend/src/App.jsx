import React, { useEffect } from 'react';
import { Header } from './components/Header';
import { Navigation } from './components/Navigation';
import { EmployeeView } from './views/employee/EmployeeView';
import { ApproverView } from './views/approver/ApproverView';
import { OpsView } from './views/ops/OpsView';
import { useExpenseStore } from './store/useExpenseStore';
import { useHitlStore } from './store/useHitlStore';
import './App.css';

export function App() {
  const activeRole = useExpenseStore((state) => state.activeRole);
  const setActiveRole = useExpenseStore((state) => state.setActiveRole);
  const checkConnection = useExpenseStore((state) => state.checkConnection);
  const loadHitlTasks = useHitlStore((state) => state.loadHitlTasks);

  // 监听浏览器 URL Hash 变化 (#employee, #approver, #ops)
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (['employee', 'approver', 'ops'].includes(hash)) {
        setActiveRole(hash);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [setActiveRole]);

  // 全局定时健康探测与待办轮询
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
        {activeRole === 'employee' && <EmployeeView />}
        {activeRole === 'approver' && <ApproverView />}
        {activeRole === 'ops' && <OpsView />}
      </main>
    </div>
  );
}

export default App;
