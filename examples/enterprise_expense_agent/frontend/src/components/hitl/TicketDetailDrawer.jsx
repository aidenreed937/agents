import React from 'react';
import { useHitlStore } from '../../store/useHitlStore';

export function TicketDetailDrawer() {
  const selectedTask = useHitlStore((state) => state.selectedTask);
  const taskDetail = useHitlStore((state) => state.taskDetail);
  const operatorRole = useHitlStore((state) => state.operatorRole);
  const setOperatorRole = useHitlStore((state) => state.setOperatorRole);
  const operatorId = useHitlStore((state) => state.operatorId);
  const setOperatorId = useHitlStore((state) => state.setOperatorId);
  const comment = useHitlStore((state) => state.comment);
  const setComment = useHitlStore((state) => state.setComment);

  const isResuming = useHitlStore((state) => state.isResuming);
  const resumeFeedback = useHitlStore((state) => state.resumeFeedback);
  const resumeTask = useHitlStore((state) => state.resumeTask);

  if (!selectedTask) {
    return (
      <div className="panel-card">
        <div className="panel-header">
          <div>
            <div className="panel-title">特批审批决策台</div>
            <div className="panel-subtitle">审核风控风险并调用 Command(resume=...) 唤醒工作流</div>
          </div>
        </div>
        <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          请从左侧列表点击选择一笔待审批单据
        </div>
      </div>
    );
  }

  const st = taskDetail?.state || {};
  const ticket = st.hitl_ticket || {};
  const claim = st.validated_claim || {};
  const risk = st.risk_assessment || {};

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <div className="panel-title">特批审批决策台</div>
          <div className="panel-subtitle">
            当前审核: <code style={{ color: 'var(--accent-cyan)' }}>{selectedTask.thread_id}</code>
          </div>
        </div>
      </div>

      <div className="result-card status-PAUSED_HITL" style={{ marginTop: 0, marginBottom: '1.25rem' }}>
        <span className="result-badge badge-warning">风控规则拦截 · 触发特批</span>
        <div className="key-value-list">
          <span className="kv-key">Thread ID:</span>
          <span className="kv-val">
            <code style={{ color: 'var(--accent-cyan)' }}>{selectedTask.thread_id}</code>
          </span>

          <span className="kv-key">审批工单编号:</span>
          <span className="kv-val">{ticket.ticket_id || 'TICKET-AUTO'}</span>

          <span className="kv-key">提报员工:</span>
          <span className="kv-val">{selectedTask.employee_id}</span>

          <span className="kv-key">申报事由:</span>
          <span className="kv-val" style={{ color: '#cbd5e1' }}>
            {selectedTask.query}
          </span>

          <span className="kv-key">城市与费用科目:</span>
          <span className="kv-val">
            {claim.city || selectedTask.city || '-'} / {claim.category || selectedTask.category || '-'}
          </span>

          <span className="kv-key">申报金额 / 政策上限:</span>
          <span className="kv-val">
            <b style={{ color: 'var(--accent-yellow)' }}>
              ¥{claim.proposed_amount || selectedTask.amount || '-'}
            </b>{' '}
            (标准限额: ¥{risk.policy_limit || claim.policy_limit || 300.0}，超标 ¥
            {risk.overlimit_amount || 0})
          </span>

          <span className="kv-key">发票代码 / 代码核验:</span>
          <span className="kv-val">
            {claim.invoice_code || selectedTask.invoice_code || '-'} (税控验真通过)
          </span>

          <span className="kv-key">数字契约指纹:</span>
          <span className="kv-val" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: '#64748b' }}>
            {claim.version_hash || 'hash-pending'}
          </span>

          <span className="kv-key">风控阻断原因:</span>
          <span className="kv-val" style={{ color: 'var(--accent-yellow)' }}>
            {ticket.reason || risk.reason || selectedTask.hitl_reason || '费用超标'}
          </span>
        </div>
      </div>

      <form onSubmit={(e) => e.preventDefault()}>
        <div className="form-group" style={{ display: 'flex', gap: '12px' }}>
          <div style={{ flex: 1 }}>
            <label className="form-label">审批人角色 (Role)</label>
            <select
              className="form-select"
              value={operatorRole}
              onChange={(e) => setOperatorRole(e.target.value)}
            >
              <option value="DIRECTOR">业务/部门总监 (DIRECTOR)</option>
              <option value="FINANCE_CLERK">财务出纳 (FINANCE_CLERK)</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label className="form-label">审批人工号</label>
            <input
              type="text"
              className="form-input"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">审批决策批注</label>
          <textarea
            className="form-textarea"
            style={{ minHeight: '70px' }}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            required
          />
        </div>

        <div style={{ display: 'flex', gap: '12px', marginTop: '1rem' }}>
          <button
            id="btnApproveHitl"
            type="button"
            className="btn-success"
            style={{ flex: 1 }}
            disabled={isResuming}
            onClick={() => resumeTask(true)}
          >
            {isResuming ? '正在唤醒 LangGraph...' : '批准并继续流转建单'}
          </button>
          <button
            id="btnRejectHitl"
            type="button"
            className="btn-danger"
            style={{ flex: 1 }}
            disabled={isResuming}
            onClick={() => resumeTask(false)}
          >
            驳回申报
          </button>
        </div>
      </form>

      {resumeFeedback && (
        <div style={{ marginTop: '1rem' }}>
          <div className={`result-card status-${resumeFeedback.type === 'success' ? 'COMPLETED' : 'REJECTED_RISK'}`}>
            <span className={`result-badge badge-${resumeFeedback.type}`}>
              {resumeFeedback.title}
            </span>
            <div style={{ fontSize: '0.85rem', marginTop: '4px' }}>
              {resumeFeedback.message}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
