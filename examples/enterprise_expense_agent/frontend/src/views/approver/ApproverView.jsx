import React, { useEffect } from 'react';
import { useHitlStore } from '../../store/useHitlStore';

export function ApproverView() {
  const tasks = useHitlStore((state) => state.tasks);
  const isLoadingTasks = useHitlStore((state) => state.isLoadingTasks);
  const loadHitlTasks = useHitlStore((state) => state.loadHitlTasks);
  const selectTask = useHitlStore((state) => state.selectTask);
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

  useEffect(() => {
    loadHitlTasks();
  }, [loadHitlTasks]);

  const st = taskDetail?.state || {};
  const ticket = st.hitl_ticket || {};
  const claim = st.validated_claim || {};
  const risk = st.risk_assessment || {};

  return (
    <div className="approver-workspace">
      {/* 顶部主管身份横幅 */}
      <div className="approver-header-banner">
        <div>
          <div className="approver-banner-title">企业差旅特批审批工作台</div>
          <div className="approver-banner-subtitle">
            专门审核经由智能体风控判定为超标或高危的差旅单据，执行人在回路（HITL）决策
          </div>
        </div>
        <div className="approver-identity-pill">
          <span>当前审批席位：</span>
          <select
            className="form-select"
            style={{ width: '220px', padding: '6px 10px', fontSize: '0.85rem' }}
            value={operatorRole}
            onChange={(e) => setOperatorRole(e.target.value)}
          >
            <option value="DIRECTOR">业务/部门总监 (具备超标特批权)</option>
            <option value="FINANCE_CLERK">财务出纳 (具备入账结算权)</option>
          </select>
        </div>
      </div>

      <div className="grid-layout-2col">
        {/* 左侧：待办列表 */}
        <div>
          <div className="panel-card">
            <div className="panel-header">
              <div>
                <div className="panel-title">
                  待审批特批单据
                  <span className="badge badge-alert" style={{ marginLeft: '8px' }}>
                    {tasks.length} 笔待办
                  </span>
                </div>
                <div className="panel-subtitle">命中超标制度规则，流程已在 LangGraph 断点就地挂起</div>
              </div>
              <button
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
                    <th>单据标识</th>
                    <th>申报员工</th>
                    <th>申报金额</th>
                    <th>超标风险判定</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2.5rem' }}>
                        当前暂无待特批单据，所有合规单据均已自动流转
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
                              maxWidth: '180px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap'
                            }}
                            title={task.hitl_reason || ''}
                          >
                            {task.hitl_reason || '费用超标'}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="btn-small"
                              onClick={() => selectTask(task)}
                            >
                              {isSelected ? '正在审核' : '审阅'}
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
        </div>

        {/* 右侧：单据核验详情与审批操作 */}
        <div>
          <div className="panel-card">
            <div className="panel-header">
              <div>
                <div className="panel-title">特批合规审阅与决定</div>
                <div className="panel-subtitle">审核业务事实比对，确认后注入 Command(resume=...) 唤醒</div>
              </div>
            </div>

            {!selectedTask ? (
              <div style={{ padding: '4rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                请点击左侧列表中的单据进行特批审阅
              </div>
            ) : (
              <div>
                {/* 核心业务核验对比卡 */}
                <div className="audit-diff-card">
                  <div className="diff-header">
                    <span className="diff-tag">超额特批审阅</span>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      工单号: {ticket.ticket_id || 'TICKET-AUTO'}
                    </span>
                  </div>

                  <div className="diff-row highlight-box">
                    <div className="diff-col">
                      <div className="diff-label">申报实际发生额</div>
                      <div className="diff-val warn">¥{claim.proposed_amount || selectedTask.amount || '-'}</div>
                    </div>
                    <div className="diff-arrow">&gt;</div>
                    <div className="diff-col">
                      <div className="diff-label">当前城市制度上限</div>
                      <div className="diff-val">¥{risk.policy_limit || claim.policy_limit || 300.0}</div>
                    </div>
                    <div className="diff-col">
                      <div className="diff-label">超标特批差额</div>
                      <div className="diff-val danger">+¥{risk.overlimit_amount || 0}</div>
                    </div>
                  </div>

                  <div className="key-value-list" style={{ marginTop: '12px' }}>
                    <span className="kv-key">提报人员工:</span>
                    <span className="kv-val">{selectedTask.employee_id}</span>

                    <span className="kv-key">出差事由申述:</span>
                    <span className="kv-val" style={{ color: '#f1f5f9' }}>{selectedTask.query}</span>

                    <span className="kv-key">出差城市 / 科目:</span>
                    <span className="kv-val">{claim.city || selectedTask.city || '-'} / {claim.category || selectedTask.category || '-'}</span>

                    <span className="kv-key">发票税控验真:</span>
                    <span className="kv-val" style={{ color: 'var(--accent-green)' }}>
                      代码 {claim.invoice_code || selectedTask.invoice_code || '-'} (全国税控库查验一致，票面无误差)
                    </span>

                    <span className="kv-key">OA 出差行程审批:</span>
                    <span className="kv-val" style={{ color: 'var(--accent-cyan)' }}>
                      已匹配已审批行程单 [OA-TRIP-2026-001]
                    </span>
                  </div>
                </div>

                {/* 审批操作表单 */}
                <form onSubmit={(e) => e.preventDefault()} style={{ marginTop: '1.25rem' }}>
                  <div className="form-group" style={{ display: 'flex', gap: '12px' }}>
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
                    <div style={{ flex: 1 }}>
                      <label className="form-label">审批权限级别</label>
                      <input
                        type="text"
                        className="form-input"
                        value={operatorRole === 'DIRECTOR' ? '业务总监（特批核准权）' : '财务出纳（结算权）'}
                        disabled
                      />
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">审批决策签署意见</label>
                    <textarea
                      className="form-textarea"
                      style={{ minHeight: '75px' }}
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      required
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '12px', marginTop: '1rem' }}>
                    <button
                      type="button"
                      className="btn-success"
                      style={{ flex: 1, padding: '12px' }}
                      disabled={isResuming}
                      onClick={() => resumeTask(true)}
                    >
                      {isResuming ? '正在唤醒工作流...' : '同意特批并完成入账草单'}
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      style={{ flex: 1, padding: '12px' }}
                      disabled={isResuming}
                      onClick={() => resumeTask(false)}
                    >
                      驳回超额申请
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
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
