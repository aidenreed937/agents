import React from 'react';
import { useExpenseStore } from '../store/useExpenseStore';
import { useHitlStore } from '../store/useHitlStore';

export function Navigation() {
  const activeTab = useExpenseStore((state) => state.activeTab);
  const setActiveTab = useExpenseStore((state) => state.setActiveTab);
  const tasks = useHitlStore((state) => state.tasks);

  const pendingCount = tasks.length;

  return (
    <nav className="nav-tabs">
      <button
        className={`tab-btn ${activeTab === 'employee' ? 'active' : ''}`}
        onClick={() => setActiveTab('employee')}
      >
        员工智能报销 (Employee Portal)
      </button>
      <button
        className={`tab-btn ${activeTab === 'hitl' ? 'active' : ''}`}
        onClick={() => setActiveTab('hitl')}
      >
        人在回路审批待办 (HITL Center)
        {pendingCount > 0 && (
          <span className="badge badge-alert" id="hitlBadge">
            {pendingCount}
          </span>
        )}
      </button>
      <button
        className={`tab-btn ${activeTab === 'graph' ? 'active' : ''}`}
        onClick={() => setActiveTab('graph')}
      >
        LangGraph 状态图与拓扑 (StateGraph)
      </button>
    </nav>
  );
}
