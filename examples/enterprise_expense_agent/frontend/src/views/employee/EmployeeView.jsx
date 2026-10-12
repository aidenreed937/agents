import React from 'react';
import { useExpenseStore } from '../../store/useExpenseStore';

const USER_FRIENDLY_STEPS = [
  { id: 'security_guardrail', title: '隐私脱敏', desc: '手机/卡号掩码' },
  { id: 'parse_intent', title: '要素提取', desc: '识别金额与城市' },
  { id: 'fetch_data_assets', title: '税控查验', desc: '比对发票真伪与行程' },
  { id: 'cross_validate_claim', title: '契约校准', desc: '发票票面事实核对' },
  { id: 'governance_check', title: '标准风控', desc: '差旅限额比对' },
  { id: 'create_draft', title: '凭证生成', desc: '建立财务预审单' }
];

export function EmployeeView() {
  const presets = useExpenseStore((state) => state.presets);
  const applyPreset = useExpenseStore((state) => state.applyPreset);
  const employeeId = useExpenseStore((state) => state.employeeId);
  const setEmployeeId = useExpenseStore((state) => state.setEmployeeId);
  const rawQuery = useExpenseStore((state) => state.rawQuery);
  const setRawQuery = useExpenseStore((state) => state.setRawQuery);

  const isSubmitting = useExpenseStore((state) => state.isSubmitting);
  const submitStream = useExpenseStore((state) => state.submitStream);
  const resetForm = useExpenseStore((state) => state.resetForm);

  const friendlyStepText = useExpenseStore((state) => state.friendlyStepText);
  const nodeStatus = useExpenseStore((state) => state.nodeStatus);
  const result = useExpenseStore((state) => state.result);
  const setActiveRole = useExpenseStore((state) => state.setActiveRole);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!rawQuery.trim() || isSubmitting) return;
    submitStream();
  };

  const draftData = result?.draft?.data || result?.draft || {};

  return (
    <div className="employee-workspace">
      {/* 顶部欢迎卡片 */}
      <div className="assistant-welcome-card">
        <div className="assistant-avatar">A</div>
        <div className="assistant-intro">
          <div className="assistant-title">智能差旅报销助手</div>
          <div className="assistant-desc">
            您好，工号 <b style={{ color: 'var(--accent-cyan)' }}>{employeeId}</b>！请直接告诉我您出差期间的消费情况（时间、地点、金额、发票号），我将自动为您验真发票、核对行程并完成合规报销。
          </div>
        </div>
      </div>

      <div className="grid-layout-2col">
        {/* 左侧：日常申报输入 */}
        <div>
          <div className="panel-card">
            <div className="panel-header">
              <div>
                <div className="panel-title">我的报销申报</div>
                <div className="panel-subtitle">支持口语化自然表达，无需繁琐手工填表</div>
              </div>
            </div>

            {/* 常见申报模板（预置场景） */}
            {presets && presets.length > 0 && (
              <div className="presets-wrap">
                <span className="presets-label">常用快捷填报模板：</span>
                <div className="presets-grid">
                  {presets.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className="preset-chip"
                      title={p.description}
                      onClick={() => applyPreset(p)}
                    >
                      <span>{p.title}</span>
                      <span className="chip-tag">{p.badge}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">申报人员工工号</label>
                <input
                  type="text"
                  className="form-input"
                  style={{ width: '220px' }}
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">消费事由描述与发票信息</label>
                <textarea
                  className="form-textarea"
                  style={{ minHeight: '120px' }}
                  placeholder="例：帮我报销2026年3月20日在北京出差的打车费220元，发票代码为 INV-2026-901"
                  value={rawQuery}
                  onChange={(e) => setRawQuery(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '1.25rem' }}>
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ padding: '12px 28px', fontSize: '0.95rem' }}
                  disabled={isSubmitting || !rawQuery.trim()}
                >
                  {isSubmitting ? '智能核验办理中...' : '提交智能报销'}
                </button>
                <button
                  type="button"
                  className="btn-small"
                  style={{ padding: '12px 20px' }}
                  onClick={resetForm}
                  disabled={isSubmitting}
                >
                  清空重新输入
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* 右侧：办理进度与结果凭证 */}
        <div>
          <div className="panel-card">
            <div className="panel-header">
              <div>
                <div className="panel-title">申报办理进度与凭证</div>
                <div className="panel-subtitle">全自动化税务与行程比对</div>
              </div>
            </div>

            {/* 拟人化执行状态动态条 */}
            {isSubmitting && (
              <div className="processing-indicator-card">
                <div className="loading-spinner"></div>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--accent-cyan)', fontSize: '0.9rem' }}>
                    {friendlyStepText || '正在办理中...'}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    系统正在自动连接税控发票中心与差旅中台核验数据
                  </div>
                </div>
              </div>
            )}

            {/* 6 阶段业务进度流程指示 */}
            <div className="friendly-steps-container">
              {USER_FRIENDLY_STEPS.map((s, idx) => {
                const st = nodeStatus[s.id] || 'waiting';
                let pillClass = 'step-pill';
                let iconText = idx + 1;
                if (st === 'done') {
                  pillClass += ' done';
                  iconText = '✓';
                } else if (st === 'running') {
                  pillClass += ' running';
                  iconText = '...';
                } else if (st === 'interrupted') {
                  pillClass += ' interrupted';
                  iconText = '!';
                } else if (st === 'blocked') {
                  pillClass += ' blocked';
                  iconText = '×';
                }

                return (
                  <div key={s.id} className={pillClass}>
                    <div className="step-circle">{iconText}</div>
                    <div className="step-content">
                      <div className="step-title">{s.title}</div>
                      <div className="step-desc">{s.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 结果呈现 */}
            {result && (
              <div style={{ marginTop: '1.5rem' }}>
                {/* 场景 1: 成功办结草单 */}
                {result.status === 'COMPLETED' && (
                  <div className="voucher-card">
                    <div className="voucher-header">
                      <div>
                        <div className="voucher-title">差旅费用报销预审凭单</div>
                        <div className="voucher-no">单号：{result.draft?.draft_id || draftData.draft_id}</div>
                      </div>
                      <span className="voucher-seal">已通过自动核销</span>
                    </div>

                    <div className="voucher-grid">
                      <div className="voucher-item">
                        <span className="voucher-label">提报员工</span>
                        <span className="voucher-value">{employeeId}</span>
                      </div>
                      <div className="voucher-item">
                        <span className="voucher-label">入账报销金额</span>
                        <span className="voucher-value highlight">¥{draftData.total_amount || '-'}</span>
                      </div>
                      <div className="voucher-item">
                        <span className="voucher-label">出差城市</span>
                        <span className="voucher-value">{draftData.destination || '-'}</span>
                      </div>
                      <div className="voucher-item">
                        <span className="voucher-label">费用科目</span>
                        <span className="voucher-value">{draftData.expense_type || '-'}</span>
                      </div>
                      <div className="voucher-item" style={{ gridColumn: 'span 2' }}>
                        <span className="voucher-label">关联发票代码</span>
                        <span className="voucher-value">{draftData.invoice_code || '-'} (税控验真通过)</span>
                      </div>
                    </div>

                    <div className="voucher-footer">
                      审批说明：{draftData.approver_comment || '标准限额内核验直通，自动建立财务预审凭单。'}
                    </div>
                  </div>
                )}

                {/* 场景 2: 费用超标挂起提示 */}
                {result.status === 'PAUSED_HITL' && (
                  <div className="hitl-notice-card">
                    <div className="hitl-notice-icon">!</div>
                    <div className="hitl-notice-content">
                      <div className="hitl-notice-title">费用超标 · 已自动为您提交特批流程</div>
                      <div className="hitl-notice-desc">
                        {result.interruptPayload?.reason || '本次申报金额超出了对应城市的报销标准上限。'}
                      </div>
                      <div style={{ marginTop: '10px' }}>
                        <button
                          type="button"
                          className="btn-primary"
                          style={{ fontSize: '0.82rem', padding: '6px 14px' }}
                          onClick={() => setActiveRole('approver')}
                        >
                          切换到「主管审批中心」代办特批体验 &rarr;
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* 场景 3: 缺少信息追问 */}
                {(result.status === 'WAITING_CLARIFICATION' || result.needsClarification) && (
                  <div className="clarify-bubble">
                    <div className="bubble-avatar">助手</div>
                    <div className="bubble-body">
                      <div className="bubble-title">还需要您补充一点信息：</div>
                      <div className="bubble-text">
                        {result.clarificationQuestion || '请补充说明您的出差城市或发票代码，以便我为您精确核准。'}
                      </div>
                    </div>
                  </div>
                )}

                {/* 场景 4: 安全与违规拦截 */}
                {(result.status === 'REJECTED_GUARDRAIL' || result.guardrailBlocked) && (
                  <div className="blocked-notice-card">
                    <div className="blocked-title">提报已被安全策略拦截</div>
                    <div className="blocked-desc">
                      检测到输入包含非规范提权或注入指令：{result.guardrailReason}
                    </div>
                  </div>
                )}

                {result.status === 'FAILED' && (
                  <div className="blocked-notice-card">
                    <div className="blocked-title">数据核验未通过</div>
                    <div className="blocked-desc">
                      发票查无此票或行程单不匹配，单据已终止自动建单。请核实您的发票真伪。
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
