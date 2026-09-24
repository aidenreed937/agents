import React, { useEffect } from 'react';
import { TaskTable } from './TaskTable';
import { TicketDetailDrawer } from './TicketDetailDrawer';
import { useHitlStore } from '../../store/useHitlStore';

export function HitlCenter() {
  const loadHitlTasks = useHitlStore((state) => state.loadHitlTasks);

  useEffect(() => {
    loadHitlTasks();
  }, [loadHitlTasks]);

  return (
    <div className="grid-layout-2col">
      <TaskTable />
      <TicketDetailDrawer />
    </div>
  );
}
