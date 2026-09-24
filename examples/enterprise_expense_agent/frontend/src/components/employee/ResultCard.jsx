import React from 'react';
import { useExpenseStore } from '../../store/useExpenseStore';

export function ResultCard() {
  const result = useExpenseStore((state) => state.result);
  const setActiveTab = useExpenseStore((state) => state.setActiveTab);

  if (!result) return null;

  const {
    status,
    draft,
    interruptPayload,
    needsClarification,
    clarificationQuestion,
    guardrailBlocked,
    guardrailReason
  } = result;

  const isSuccess = status === 'COMPLETED';
  const isHitl = status === 'PAUSED_HITL';
  const isClarify = status === 'WAITING_CLARIFICATION' || needsClarification;
  const isBlocked = status === 'REJECTED_GUARDRAIL' || guardrailBlocked;

  const draftData = draft?.data || draft || {};

  return (
    <div id="resultCard" className={`result-card status-${status}`}>
      {isSuccess && (
        <div>
          <span className="result-badge badge-success">核销通过 · 财务草单已生成</span>
          <div className="key-value-list">
            <span className="kv-key">报销草单单号:</span>
            <span className="kv-val">
              <b style={{ color: 'var(--accent-green)' }}>
                {draft?.draft_id || draftData.draft_id}
              </b>
            </span>

            <span className="kv-key">入账报销金额:</span>
            <span className="kv-val">¥{draftData.total_amount || '-'}</span>

            <span className="kv-key">发票代码 / 城市:</span>
            <span className="kv-val">
              {draftData.invoice_code || '-'} / {draftData.destination || '-'}
            </span>

            <span className="kv-key">审批备注文书:</span>
            <span className="kv-val">{draftData.approver_comment || '-'}</span>
          </div>
        </div>
      )}

      {isHitl && (
        <div>
          <span className="result-badge badge-warning">费用超标 · 已进入人在回路 (HITL) 审批流程</span>
          <p style={{ fontSize: '0.85rem', marginTop: '6px', color: '#cbd5e1' }}>
            {interruptPayload?.reason || '费用超过城市制度限额，流程已就地挂起。'}
          </p>
          <div style={{ marginTop: '10px' }}>
            <button
              type="button"
              className="btn-primary"
              style={{ fontSize: '0.8rem', padding: '6px 14px' }}
              onClick={() => setActiveTab('hitl')}
            >
              前往「人在回路审批中心」特批处理 &rarr;
            </button>
          </div>
        </div>
      )}

      {isClarify && (
        <div>
          <span className="result-badge badge-info">要素不全 · 反问澄清模式生效</span>
          <p style={{ fontSize: '0.88rem', marginTop: '8px', color: 'var(--accent-cyan)', fontWeight: 500 }}>
            问答追问：{clarificationQuestion || '请补充出差城市与有效发票代码'}
          </p>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            （智能体严格遵循确定性平衡原则，拒绝无中生有和幻觉脑补）
          </p>
        </div>
      )}

      {isBlocked && (
        <div>
          <span className="result-badge badge-danger">安全防护拦截 · 提示词注入攻击</span>
          <p style={{ fontSize: '0.85rem', marginTop: '6px', color: 'var(--accent-red)' }}>
            理由: {guardrailReason || '检测到越狱或提示词劫持指令'}
          </p>
        </div>
      )}

      {!isSuccess && !isHitl && !isClarify && !isBlocked && (
        <div>
          <span className="result-badge badge-danger">核验未通过 / 风控阻断 [{status}]</span>
          <p style={{ fontSize: '0.85rem', marginTop: '6px', color: '#cbd5e1' }}>
            未能完成自动报销建单，单据已归档。请核实输入发票或行程状态。
          </p>
        </div>
      )}
    </div>
  );
}
