/**
 * 集中式 API 服务封装模块
 * 统一管理 RESTful 请求与 Server-Sent Events (SSE) 流式长连接。
 */

let currentBaseUrl = 'http://127.0.0.1:8000';

export function setBaseUrl(url) {
  currentBaseUrl = url.trim().replace(/\/$/, '');
}

export function getBaseUrl() {
  return currentBaseUrl;
}

export async function checkHealth() {
  const res = await fetch(`${currentBaseUrl}/api/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return await res.json();
}

export async function fetchPresets() {
  const res = await fetch(`${currentBaseUrl}/api/expense/presets`);
  if (!res.ok) throw new Error(`Fetch presets failed: ${res.status}`);
  return await res.json();
}

export async function fetchGraphTopology() {
  const res = await fetch(`${currentBaseUrl}/api/expense/graph`);
  if (!res.ok) throw new Error(`Fetch graph failed: ${res.status}`);
  return await res.json();
}

export async function submitExpenseSync({ threadId, employeeId, query }) {
  const res = await fetch(`${currentBaseUrl}/api/expense/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      employee_id: employeeId,
      query: query
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Submit failed');
  }
  return await res.json();
}

export async function fetchTasks(status = null) {
  const url = status
    ? `${currentBaseUrl}/api/expense/tasks?status=${encodeURIComponent(status)}`
    : `${currentBaseUrl}/api/expense/tasks`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Fetch tasks failed: ${res.status}`);
  return await res.json();
}

export async function fetchTaskDetail(threadId) {
  const res = await fetch(`${currentBaseUrl}/api/expense/task/${encodeURIComponent(threadId)}`);
  if (!res.ok) throw new Error(`Fetch task detail failed: ${res.status}`);
  return await res.json();
}

export async function resumeHitlTask({ threadId, operatorRole, operatorId, approved, comment }) {
  const res = await fetch(`${currentBaseUrl}/api/expense/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      operator_role: operatorRole,
      operator_id: operatorId,
      approved: approved,
      comment: comment
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Resume failed');
  }
  return await res.json();
}

export function subscribeExpenseStream({ query, employeeId, threadId }, callbacks) {
  const url = `${currentBaseUrl}/api/expense/submit-stream?query=${encodeURIComponent(
    query
  )}&employee_id=${encodeURIComponent(employeeId)}&thread_id=${encodeURIComponent(threadId)}`;

  const es = new EventSource(url);

  es.addEventListener('workflow_started', (e) => {
    callbacks.onWorkflowStarted?.(JSON.parse(e.data));
  });

  es.addEventListener('node_executed', (e) => {
    callbacks.onNodeExecuted?.(JSON.parse(e.data));
  });

  es.addEventListener('hitl_interrupted', (e) => {
    callbacks.onHitlInterrupted?.(JSON.parse(e.data));
    es.close();
  });

  es.addEventListener('workflow_finished', (e) => {
    callbacks.onWorkflowFinished?.(JSON.parse(e.data));
    es.close();
  });

  es.onerror = (err) => {
    callbacks.onError?.(err);
    es.close();
  };

  return () => {
    es.close();
  };
}
