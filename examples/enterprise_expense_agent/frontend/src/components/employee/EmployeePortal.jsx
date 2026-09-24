import React from 'react';
import { PresetSelector } from './PresetSelector';
import { ExpenseForm } from './ExpenseForm';
import { PipelineVisualizer } from './PipelineVisualizer';
import { LiveTerminal } from './LiveTerminal';
import { ResultCard } from './ResultCard';
import { useExpenseStore } from '../../store/useExpenseStore';

export function EmployeePortal() {
  const currentStatus = useExpenseStore((state) => state.currentStatus);

  return (
    <div className="grid-layout-2col">
      {/* 左侧输入卡片 */}
      <div>
        <div className="panel-card">
          <div className="panel-header">
            <div>
              <div className="panel-title">智能提报入口</div>
              <div className="panel-subtitle">支持自然语言口语化描述，后端由 LangGraph 状态图驱动</div>
            </div>
          </div>
          <PresetSelector />
          <ExpenseForm />
        </div>
      </div>

      {/* 右侧流程执行与终端反馈 */}
      <div>
        <div className="panel-card">
          <div className="panel-header">
            <div>
              <div className="panel-title">LangGraph 节点流转监控</div>
              <div className="panel-subtitle">全链路节点状态与事件实时可视化</div>
            </div>
            <span
              id="currentStatusBadge"
              className={`badge ${
                currentStatus === 'COMPLETED'
                  ? 'badge-success'
                  : currentStatus.startsWith('REJECTED') || currentStatus === 'PAUSED_HITL'
                  ? 'badge-alert'
                  : ''
              }`}
            >
              {currentStatus}
            </span>
          </div>

          <PipelineVisualizer />
          <LiveTerminal />
          <ResultCard />
        </div>
      </div>
    </div>
  );
}
