import React, { useState, useEffect } from 'react';
import { fetchGraphTopology, fetchTasks } from '../../services/api';
import { useExpenseStore } from '../../store/useExpenseStore';
import { MermaidViewer } from '../../components/MermaidViewer';

export function OpsView() {
  const engineInfo = useExpenseStore((state) => state.engineInfo);
  const backendUrl = useExpenseStore((state) => state.backendUrl);
  const logs = useExpenseStore((state) => state.logs);

  const [mermaidSrc, setMermaidSrc] = useState('加载中...');
  const [allTasks, setAllTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [graphData, tasksData] = await Promise.all([
        fetchGraphTopology().catch((e) => ({ mermaid: e.message })),
        fetchTasks().catch(() => [])
      ]);
      setMermaidSrc(graphData.mermaid || '未能加载 Mermaid 拓扑');
      setAllTasks(tasksData || []);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="ops-workspace">
      {/* 顶部运维看板横幅 */}
      <div className="ops-header-banner">
        <div>
          <div className="ops-banner-title">LangGraph 运行时架构监控与链路审计</div>
          <div className="ops-banner-subtitle">
            用于 IT 架构师与安全运维实时监控 StateGraph 执行拓扑、检查点通道（Channels）与快照落盘状态
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button type="button" className="btn-small" onClick={loadData} disabled={isLoading}>
            {isLoading ? '刷新中...' : '刷新拓扑与快照'}
          </button>
        </div>
      </div>

      <div className="grid-layout-2col">
        {/* 左侧：LangGraph 拓扑图与纯函数契约 */}
        <div>
          <div className="panel-card">
            <div className="panel-header">
              <div>
                <div className="panel-title">8 大节点拓扑与纯函数契约</div>
                <div className="panel-subtitle">
                  代码定义: <code style={{ color: 'var(--accent-cyan)' }}>src/enterprise_expense_agent/agent/workflow.py:24</code>
                </div>
              </div>
            </div>

            <div className="key-value-list" style={{ gridTemplateColumns: '170px 1fr', rowGap: '8px', fontSize: '0.8rem' }}>
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

            <h4 style={{ fontSize: '0.88rem', margin: '1.25rem 0 8px 0', color: 'var(--accent-cyan)' }}>
              Mermaid 状态机拓扑渲染
            </h4>
            <MermaidViewer chart={mermaidSrc} />
          </div>
        </div>

        {/* 右侧：实时底层执行 Trace 日志与持久化检查点 */}
        <div>
          <div className="panel-card">
            <div className="panel-header">
              <div>
                <div className="panel-title">底层执行 Trace 实时流</div>
                <div className="panel-subtitle">包含 SSE 节点触发、PII 掩码与风控规则计算记录</div>
              </div>
            </div>

            <div className="terminal-window" style={{ maxHeight: '260px' }}>
              {logs.map((log) => {
                let textCls = '';
                if (log.type === 'highlight') textCls = 'log-text-highlight';
                if (log.type === 'warn') textCls = 'log-text-warn';
                if (log.type === 'danger') textCls = 'log-text-danger';

                return (
                  <div key={log.id} className="log-entry">
                    <span className="log-time">[{log.time}]</span>
                    <span className="log-node">&lt;{log.node}&gt;</span>
                    <span className={textCls}>{log.text}</span>
                  </div>
                );
              })}
            </div>

            <h4 style={{ fontSize: '0.88rem', margin: '1.25rem 0 8px 0', color: 'var(--accent-cyan)' }}>
              持久化检查点快照记录 (Checkpoints: {allTasks.length} 项)
            </h4>
            <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
              <table className="tasks-table">
                <thead>
                  <tr>
                    <th>Thread ID</th>
                    <th>工号</th>
                    <th>当前状态</th>
                    <th>更新时间</th>
                  </tr>
                </thead>
                <tbody>
                  {allTasks.length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                        暂无检查点记录
                      </td>
                    </tr>
                  ) : (
                    allTasks.slice(0, 10).map((t) => (
                      <tr key={t.thread_id}>
                        <td><code style={{ color: 'var(--accent-cyan)', fontSize: '0.76rem' }}>{t.thread_id}</code></td>
                        <td>{t.employee_id}</td>
                        <td>
                          <span className={`badge ${t.status === 'COMPLETED' ? 'badge-success' : t.status === 'PAUSED_HITL' ? 'badge-alert' : ''}`}>
                            {t.status}
                          </span>
                        </td>
                        <td style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>{t.updated_at}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
