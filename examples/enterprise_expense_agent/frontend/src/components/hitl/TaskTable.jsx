import React from 'react';
import { useHitlStore } from '../../store/useHitlStore';

export function TaskTable() {
  const tasks = useHitlStore((state) => state.tasks);
  const isLoadingTasks = useHitlStore((state) => state.isLoadingTasks);
  const loadHitlTasks = useHitlStore((state) => state.loadHitlTasks);
  const selectTask = useHitlStore((state) => state.selectTask);
  const selectedTask = useHitlStore((state) => state.selectedTask);

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <div className="panel-title">挂起待审批工单 (PAUSED_HITL)</div>
          <div className="panel-subtitle">LangGraph interrupt() 挂起的任务，快照已保存在磁盘/数据库</div>
        </div>
        <button
          id="btnRefreshTasks"
          type="button"
          className="btn-small"
          onClick={loadHitlTasks}
          disabled={isLoadingTasks}
        >
          {isLoadingTasks ? '刷新中...' : '刷新待办'}
        </button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="tasks-table">
          <thead>
            <tr>
              <th>Thread ID</th>
              <th>提报人</th>
              <th>消费金额</th>
              <th>超标/原因</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody id="hitlTasksTableBody">
            {tasks.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                  当前没有处于 PAUSED_HITL 挂起状态的审批单据
                </td>
              </tr>
            ) : (
              tasks.map((task) => {
                const isSelected = selectedTask?.thread_id === task.thread_id;
                return (
                  <tr
                    key={task.thread_id}
                    style={isSelected ? { backgroundColor: 'rgba(56, 189, 248, 0.08)' } : {}}
                  >
                    <td>
                      <code style={{ color: 'var(--accent-cyan)', fontSize: '0.8rem' }}>
                        {task.thread_id}
                      </code>
                    </td>
                    <td>{task.employee_id || '-'}</td>
                    <td style={{ color: 'var(--accent-yellow)', fontWeight: 600 }}>
                      ¥{task.amount || '-'}
                    </td>
                    <td
                      style={{
                        fontSize: '0.8rem',
                        maxWidth: '220px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                      title={task.hitl_reason || ''}
                    >
                      {task.hitl_reason || '超额特批'}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn-small"
                        onClick={() => selectTask(task)}
                      >
                        {isSelected ? '审核中' : '审核'}
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
