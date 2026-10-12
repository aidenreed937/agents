import React from 'react';
import { useExpenseStore } from '../store/useExpenseStore';
import { useHitlStore } from '../store/useHitlStore';

export function Navigation() {
  const activeRole = useExpenseStore((state) => state.activeRole);
  const setActiveRole = useExpenseStore((state) => state.setActiveRole);
  const tasks = useHitlStore((state) => state.tasks);

  const pendingCount = tasks.length;

  return (
    <nav className="nav-tabs">
      <button
        type="button"
        className={`tab-btn ${activeRole === 'employee' ? 'active' : ''}`}
        onClick={() => setActiveRole('employee')}
      >
        <span>员工智能报销端 (Employee App)</span>
      </button>

      <button
        type="button"
        className={`tab-btn ${activeRole === 'approver' ? 'active' : ''}`}
        onClick={() => setActiveRole('approver')}
      >
        <span>主管与财务审批中心 (Approval Portal)</span>
        {pendingCount > 0 && (
          <span className="badge badge-alert" id="hitlBadge">
            {pendingCount} 待特批
          </span>
        )}
      </button>

      <button
        type="button"
        className={`tab-btn ${activeRole === 'ops' ? 'active' : ''}`}
        onClick={() => setActiveRole('ops')}
      >
        <span>运维与可观测大盘 (Ops & Diagnostics)</span>
      </button>
    </nav>
  );
}
