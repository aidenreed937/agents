import React from 'react';
import { useExpenseStore } from '../../store/useExpenseStore';

export function ExpenseForm() {
  const employeeId = useExpenseStore((state) => state.employeeId);
  const setEmployeeId = useExpenseStore((state) => state.setEmployeeId);
  const threadId = useExpenseStore((state) => state.threadId);
  const setThreadId = useExpenseStore((state) => state.setThreadId);
  const rawQuery = useExpenseStore((state) => state.rawQuery);
  const setRawQuery = useExpenseStore((state) => state.setRawQuery);

  const isSubmitting = useExpenseStore((state) => state.isSubmitting);
  const submitStream = useExpenseStore((state) => state.submitStream);
  const submitSync = useExpenseStore((state) => state.submitSync);
  const resetForm = useExpenseStore((state) => state.resetForm);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!rawQuery.trim() || isSubmitting) return;
    submitStream();
  };

  return (
    <form id="expenseForm" onSubmit={handleSubmit}>
      <div className="form-group" style={{ display: 'flex', gap: '12px' }}>
        <div style={{ flex: 1 }}>
          <label className="form-label">员工工号 (Employee ID)</label>
          <input
            id="employeeIdInput"
            type="text"
            className="form-input"
            value={employeeId}
            onChange={(e) => setEmployeeId(e.target.value)}
            required
          />
        </div>
        <div style={{ flex: 1 }}>
          <label className="form-label">线程 ID (Thread ID / 留空自动生成)</label>
          <input
            id="threadIdInput"
            type="text"
            className="form-input"
            placeholder="自动生成或自定义"
            value={threadId}
            onChange={(e) => setThreadId(e.target.value)}
          />
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">自然语言报销诉求</label>
        <textarea
          id="rawQueryInput"
          className="form-textarea"
          placeholder="例：帮我报销2026年3月20日在北京出差的打车费220元，发票代码为 INV-2026-901"
          value={rawQuery}
          onChange={(e) => setRawQuery(e.target.value)}
          required
        />
      </div>

      <div style={{ display: 'flex', gap: '12px', marginTop: '1rem' }}>
        <button
          type="submit"
          id="btnSubmitStream"
          className="btn-primary"
          disabled={isSubmitting || !rawQuery.trim()}
        >
          <span>{isSubmitting ? '流式执行中...' : '流式实时执行 (SSE Stream)'}</span>
        </button>
        <button
          type="button"
          id="btnSubmitSync"
          className="btn-small"
          style={{ padding: '10px 16px' }}
          disabled={isSubmitting || !rawQuery.trim()}
          onClick={submitSync}
        >
          <span>同步执行</span>
        </button>
        <button
          type="button"
          id="btnClearForm"
          className="btn-small"
          style={{ padding: '10px 16px' }}
          onClick={resetForm}
        >
          <span>重置</span>
        </button>
      </div>
    </form>
  );
}
