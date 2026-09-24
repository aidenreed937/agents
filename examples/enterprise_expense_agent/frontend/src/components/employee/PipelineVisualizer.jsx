import React from 'react';
import { useExpenseStore } from '../../store/useExpenseStore';

const PIPELINE_NODES = [
  { id: 'security_guardrail', name: '1. 安全防火墙' },
  { id: 'parse_intent', name: '2. 模型要素抽取' },
  { id: 'fetch_data_assets', name: '3. 数据中台核验' },
  { id: 'cross_validate_claim', name: '4. 交叉合规比对' },
  { id: 'governance_check', name: '5. 风控与HITL' },
  { id: 'create_draft', name: '6. 幂等草单生成' }
];

export function PipelineVisualizer() {
  const nodeStatus = useExpenseStore((state) => state.nodeStatus);

  const getStatusText = (status) => {
    switch (status) {
      case 'running':
        return 'RUNNING...';
      case 'done':
        return 'DONE';
      case 'interrupted':
        return 'HITL PAUSED';
      case 'blocked':
        return 'BLOCKED';
      default:
        return 'WAITING';
    }
  };

  return (
    <div className="pipeline-bar" id="pipelineBar">
      {PIPELINE_NODES.map((node) => {
        const status = nodeStatus[node.id] || 'waiting';
        return (
          <div
            key={node.id}
            id={`node-${node.id}`}
            className={`pipeline-node ${status}`}
          >
            <div className="pipeline-node-name">{node.name}</div>
            <div className="pipeline-node-status">{getStatusText(status)}</div>
          </div>
        );
      })}
    </div>
  );
}
