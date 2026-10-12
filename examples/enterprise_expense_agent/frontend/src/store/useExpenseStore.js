import { create } from 'zustand';
import {
  setBaseUrl,
  checkHealth,
  fetchPresets,
  submitExpenseSync,
  subscribeExpenseStream
} from '../services/api';

const INITIAL_NODES = {
  security_guardrail: 'waiting',
  parse_intent: 'waiting',
  fetch_data_assets: 'waiting',
  cross_validate_claim: 'waiting',
  governance_check: 'waiting',
  create_draft: 'waiting'
};

const FRIENDLY_STEP_MAPPING = {
  security_guardrail: '正在进行数据安全检查与隐私信息脱敏...',
  parse_intent: '正在智能理解您的报销意图并抽取金额、发票要素...',
  fetch_data_assets: '正在同步查询全国税控发票库与 OA 出差行程单...',
  cross_validate_claim: '正在交叉比对发票票面与实际行程事实，生成权威申请契约...',
  governance_check: '正在核验企业差旅标准与风控合规额度...',
  create_draft: '所有校验已通过，正在生成财务预审草单凭证...'
};

// 获取初始角色（支持从 URL Hash 读取：#employee, #approver, #ops）
const getInitialRole = () => {
  const hash = window.location.hash.replace('#', '').toLowerCase();
  if (['employee', 'approver', 'ops'].includes(hash)) {
    return hash;
  }
  return 'employee';
};

export const useExpenseStore = create((set, get) => ({
  // 独立角色视角: 'employee' (员工端) | 'approver' (审批端) | 'ops' (运维端)
  activeRole: getInitialRole(),

  // 连接与服务状态
  backendUrl: 'http://127.0.0.1:8000',
  isConnected: false,
  engineInfo: '',

  // 预置场景
  presets: [],

  // 表单状态
  employeeId: 'EMP-1001',
  threadId: '',
  rawQuery: '',
  isSubmitting: false,
  currentStatus: 'IDLE',
  friendlyStepText: '',

  // 节点流水线状态 (运维与底层调用)
  nodeStatus: { ...INITIAL_NODES },

  // 终端实时日志 (运维端展示)
  logs: [
    {
      id: 'init-1',
      time: new Date().toTimeString().split(' ')[0],
      node: 'CONSOLE',
      text: '前端 React 状态脚手架已就绪，正在连接后端...',
      type: 'normal'
    }
  ],

  // 最终处理结果
  result: null,

  // 动作
  setActiveRole: (role) => {
    window.location.hash = role;
    set({ activeRole: role });
  },

  setBackendUrl: (url) => {
    setBaseUrl(url);
    set({ backendUrl: url });
    get().checkConnection();
  },

  checkConnection: async () => {
    try {
      const data = await checkHealth();
      set({
        isConnected: true,
        engineInfo: `${data.engine} (${data.durable_checkpointer})`
      });
      if (get().presets.length === 0) {
        get().loadPresets();
      }
    } catch (e) {
      set({
        isConnected: false,
        engineInfo: '连接中断'
      });
    }
  },

  loadPresets: async () => {
    try {
      const presets = await fetchPresets();
      set({ presets });
    } catch (e) {
      console.warn('Load presets error:', e);
    }
  },

  setEmployeeId: (id) => set({ employeeId: id }),
  setThreadId: (id) => set({ threadId: id }),
  setRawQuery: (query) => set({ rawQuery: query }),

  applyPreset: (preset) => {
    const randomSuffix = Math.random().toString(36).substring(2, 6);
    set({
      employeeId: preset.employee_id,
      rawQuery: preset.query,
      threadId: `th_${preset.id.replace('scenario_', '')}_${randomSuffix}`
    });
  },

  resetForm: () => {
    set({
      rawQuery: '',
      threadId: '',
      currentStatus: 'IDLE',
      friendlyStepText: '',
      nodeStatus: { ...INITIAL_NODES },
      result: null,
      logs: [
        {
          id: `log-${Date.now()}`,
          time: new Date().toTimeString().split(' ')[0],
          node: 'CONSOLE',
          text: '表单已重置，等待提报...',
          type: 'normal'
        }
      ]
    });
  },

  appendLog: (node, text, type = 'normal') => {
    const newEntry = {
      id: `log-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      time: new Date().toTimeString().split(' ')[0],
      node,
      text,
      type
    };
    set((state) => ({ logs: [...state.logs, newEntry] }));
  },

  submitStream: () => {
    const { employeeId, rawQuery, appendLog } = get();
    let threadId = get().threadId.trim();
    if (!threadId) {
      threadId = `th_${Math.random().toString(36).substring(2, 9)}`;
      set({ threadId });
    }

    set({
      isSubmitting: true,
      currentStatus: 'RUNNING',
      friendlyStepText: '系统正在启动报销流程...',
      nodeStatus: { ...INITIAL_NODES },
      result: null,
      logs: []
    });

    appendLog('SYSTEM', `建立 SSE 通道，启动 LangGraph 状态图 [Thread: ${threadId}]...`);

    const unsubscribe = subscribeExpenseStream(
      { query: rawQuery, employeeId, threadId },
      {
        onWorkflowStarted: (data) => {
          appendLog('WORKFLOW', data.message);
          set({ friendlyStepText: '智能财务助理已介入，正在核验申报信息...' });
        },
        onNodeExecuted: (data) => {
          const { node, status, new_logs } = data;
          const friendly = FRIENDLY_STEP_MAPPING[node] || '正在处理中...';
          set((s) => ({
            currentStatus: status,
            friendlyStepText: friendly,
            nodeStatus: {
              ...s.nodeStatus,
              [node]: status.startsWith('REJECTED') ? 'blocked' : 'done'
            }
          }));

          if (new_logs && new_logs.length > 0) {
            new_logs.forEach((log) => appendLog(node, log));
          }
        },
        onHitlInterrupted: (data) => {
          set((s) => ({
            isSubmitting: false,
            currentStatus: 'PAUSED_HITL',
            friendlyStepText: '费用已超出常规标准，已自动转入【主管特批审批流程】。',
            nodeStatus: {
              ...s.nodeStatus,
              governance_check: 'interrupted'
            },
            result: {
              status: 'PAUSED_HITL',
              threadId,
              interruptPayload: data.interrupt_payload
            }
          }));
          appendLog('HITL', `【人在回路触发】${data.message}`, 'warn');
        },
        onWorkflowFinished: (data) => {
          const isSuccess = data.final_status === 'COMPLETED';
          set((s) => ({
            isSubmitting: false,
            currentStatus: data.final_status,
            friendlyStepText: isSuccess
              ? '报销处理完成，已生成正式财务预审凭证！'
              : `提报处理结束，当前状态: [${data.final_status}]`,
            nodeStatus: {
              ...s.nodeStatus,
              create_draft: isSuccess ? 'done' : s.nodeStatus.create_draft
            },
            result: {
              status: data.final_status,
              threadId,
              draft: data.draft,
              needsClarification: data.needs_clarification,
              clarificationQuestion: data.clarification_question,
              guardrailBlocked: data.guardrail_blocked,
              guardrailReason: data.guardrail_reason
            }
          }));

          if (isSuccess) {
            appendLog('COMPLETED', `报销成功闭环！草单ID: ${data.draft?.draft_id}`, 'highlight');
          } else {
            appendLog('STATUS', `流程已终止，最终状态: [${data.final_status}]`, 'danger');
          }
        },
        onError: (err) => {
          set({
            isSubmitting: false,
            friendlyStepText: '通信连接中断，请检查后端服务。'
          });
          appendLog('ERROR', 'SSE 通信结束或异常中断', 'danger');
        }
      }
    );

    return unsubscribe;
  },

  submitSync: async () => {
    const { employeeId, rawQuery, appendLog } = get();
    let threadId = get().threadId.trim();
    if (!threadId) {
      threadId = `th_${Math.random().toString(36).substring(2, 9)}`;
      set({ threadId });
    }

    set({
      isSubmitting: true,
      currentStatus: 'RUNNING',
      friendlyStepText: '正在同步提交报销申请...',
      nodeStatus: { ...INITIAL_NODES },
      result: null,
      logs: []
    });

    appendLog('SYNC', `发送同步请求 POST /api/expense/submit [Thread: ${threadId}]...`);

    try {
      const data = await submitExpenseSync({ threadId, employeeId, query: rawQuery });
      const finalState = data.state || {};
      const logs = finalState.step_logs || [];
      logs.forEach((l) => appendLog('LOG', l));

      set({
        isSubmitting: false,
        currentStatus: data.status,
        friendlyStepText: '提报处理完成。',
        result: {
          status: data.status,
          threadId,
          draft: finalState.reimbursement_draft,
          needsClarification: finalState.needs_clarification,
          clarificationQuestion: finalState.clarification_question,
          hitlTicket: finalState.hitl_ticket
        }
      });
      appendLog('SYNC', `执行完毕，状态: ${data.status}`);
    } catch (e) {
      set({
        isSubmitting: false,
        friendlyStepText: '提交失败。'
      });
      appendLog('ERROR', `同步执行失败: ${e.message}`, 'danger');
    }
  }
}));
