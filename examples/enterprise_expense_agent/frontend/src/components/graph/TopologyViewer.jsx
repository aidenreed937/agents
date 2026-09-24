import React, { useState, useEffect } from 'react';
import { fetchGraphTopology } from '../../services/api';

export function TopologyViewer() {
  const [mermaidSrc, setMermaidSrc] = useState('加载中...');
  const [isLoading, setIsLoading] = useState(false);

  const loadGraph = async () => {
    setIsLoading(true);
    try {
      const data = await fetchGraphTopology();
      setMermaidSrc(data.mermaid || '未能加载 Mermaid 拓扑');
    } catch (e) {
      setMermaidSrc('加载拓扑图异常: ' + e.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadGraph();
  }, []);

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <div className="panel-title">LangGraph 原生编译拓扑结构</div>
          <div className="panel-subtitle">
            源码位置: <code style={{ color: 'var(--accent-cyan)' }}>examples/enterprise_expense_agent/src/enterprise_expense_agent/agent/workflow.py:24</code>
          </div>
        </div>
        <button
          type="button"
          className="btn-small"
          onClick={loadGraph}
          disabled={isLoading}
        >
          {isLoading ? '加载中...' : '重新加载拓扑图'}
        </button>
      </div>

      <div className="grid-layout-2col">
        <div>
          <h4 style={{ fontSize: '0.9rem', marginBottom: '8px', color: 'var(--accent-cyan)' }}>
            8 大节点与纯函数契约
          </h4>
          <div
            className="key-value-list"
            style={{ gridTemplateColumns: '180px 1fr', rowGap: '10px', fontSize: '0.8rem' }}
          >
            <span className="kv-key">1. security_guardrail</span>
            <span className="kv-val">PII 敏感项识别脱敏 + 提示词注入/越狱审查</span>

            <span className="kv-key">2. parse_intent</span>
            <span className="kv-val">版本化 Prompt 单模型提取要素 + 缺失项反问追问</span>

            <span className="kv-key">3. fetch_data_assets</span>
            <span className="kv-val">并行查询税局发票库、OA 出差行程库、差旅政策库</span>

            <span className="kv-key">4. cross_validate_claim</span>
            <span className="kv-val">业务事实强校验，以发票为准纠偏口语估算，生成不可变契约</span>

            <span className="kv-key">5. governance_check</span>
            <span className="kv-val">确定性规则计算超标差额与合规违规项判定</span>

            <span className="kv-key">6. prepare_hitl</span>
            <span className="kv-val">组装带数字指纹的审批工单 (ApprovalTicket)</span>

            <span className="kv-key">7. wait_for_hitl</span>
            <span className="kv-val">调用 LangGraph 原生 interrupt() 就地断点挂起，等待人工决策</span>

            <span className="kv-key">8. create_draft</span>
            <span className="kv-val">基于 claim_version_hash 执行两阶段幂等草单创建</span>
          </div>
        </div>

        <div>
          <h4 style={{ fontSize: '0.9rem', marginBottom: '8px', color: 'var(--accent-cyan)' }}>
            Mermaid 拓扑源码
          </h4>
          <div className="terminal-window" style={{ maxHeight: '380px' }}>
            <pre id="mermaidCodeBlock" style={{ color: '#94a3b8', fontSize: '0.76rem', whiteSpace: 'pre-wrap' }}>
              {mermaidSrc}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
