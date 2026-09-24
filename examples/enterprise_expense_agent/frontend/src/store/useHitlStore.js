import { create } from 'zustand';
import { fetchTasks, fetchTaskDetail, resumeHitlTask } from '../services/api';

export const useHitlStore = create((set, get) => ({
  tasks: [],
  isLoadingTasks: false,
  selectedTask: null,
  taskDetail: null,

  // 审批表单
  operatorRole: 'DIRECTOR',
  operatorId: 'DIR-9001',
  comment: '经核实出差事由紧急且属业务必需，同意超标特批报销。',
  isResuming: false,
  resumeFeedback: null,

  setOperatorRole: (role) => set({ operatorRole: role }),
  setOperatorId: (id) => set({ operatorId: id }),
  setComment: (comment) => set({ comment }),

  loadHitlTasks: async () => {
    set({ isLoadingTasks: true });
    try {
      const tasks = await fetchTasks('PAUSED_HITL');
      set({ tasks, isLoadingTasks: false });

      // 如果当前选中的任务已经不在列表中，清空详情
      const currentSelected = get().selectedTask;
      if (currentSelected && !tasks.some((t) => t.thread_id === currentSelected.thread_id)) {
        set({ selectedTask: null, taskDetail: null });
      }
    } catch (e) {
      console.warn('Failed to load HITL tasks:', e);
      set({ isLoadingTasks: false });
    }
  },

  selectTask: async (task) => {
    set({ selectedTask: task, resumeFeedback: null });
    try {
      const detail = await fetchTaskDetail(task.thread_id);
      set({ taskDetail: detail });
    } catch (e) {
      set({ taskDetail: task });
    }
  },

  resumeTask: async (approved) => {
    const { selectedTask, operatorRole, operatorId, comment } = get();
    if (!selectedTask) return;

    set({ isResuming: true, resumeFeedback: null });

    try {
      const res = await resumeHitlTask({
        threadId: selectedTask.thread_id,
        operatorRole,
        operatorId,
        approved,
        comment
      });

      if (res.new_status === 'COMPLETED') {
        set({
          isResuming: false,
          resumeFeedback: {
            type: 'success',
            title: '特批成功 · 财务草单已生成',
            message: `已通过 Command(resume=...) 唤醒 LangGraph 状态机并生成财务草单：${
              res.draft?.draft_id || 'DRAFT-CREATED'
            }，终审金额: ¥${res.draft?.data?.total_amount || res.draft?.total_amount || '-'}`,
            draft: res.draft
          }
        });
      } else {
        set({
          isResuming: false,
          resumeFeedback: {
            type: 'danger',
            title: '申报已被主管驳回',
            message: '状态机已迁移至 REJECTED_HITL 并安全归档。'
          }
        });
      }

      // 重新拉取待办列表
      get().loadHitlTasks();
    } catch (err) {
      set({
        isResuming: false,
        resumeFeedback: {
          type: 'danger',
          title: '人在回路恢复执行失败',
          message: err.message
        }
      });
    }
  }
}));
