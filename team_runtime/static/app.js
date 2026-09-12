(() => {
  "use strict";

  const tokenNode = document.querySelector('meta[name="team-token"]');
  const token = tokenNode ? tokenNode.getAttribute("content") || "" : "";
  const state = {
    snapshot: null,
    selectedPlanId: null,
    selectedRunId: null,
    answers: Object.create(null),
    loading: false,
    jobId: null,
  };

  const el = {
    briefForm: document.getElementById("brief-form"),
    repository: document.getElementById("repository"),
    brief: document.getElementById("brief"),
    proposeStatus: document.getElementById("propose-status"),
    plans: document.getElementById("plans-list"),
    planDetail: document.getElementById("plan-detail"),
    runs: document.getElementById("runs-list"),
    runDetail: document.getElementById("run-detail"),
    connection: document.getElementById("connection-status"),
    snapshotTime: document.getElementById("snapshot-time"),
    refresh: document.getElementById("refresh-button"),
  };

  const statusLabels = {
    queued: "排队中",
    running: "运行中",
    proposed: "待审阅",
    planning: "规划中",
    draft: "草稿",
    "needs-input": "需澄清",
    approved: "已授权",
    authorized: "已授权",
    created: "已创建",
    ready: "待授权",
    pending: "等待中",
    paused: "已暂停",
    cancelling: "取消中",
    "pause-requested": "暂停请求中",
    "cancel-requested": "取消请求中",
    resuming: "恢复中",
    verifying: "验收中",
    supervising: "方向审查中",
    repairing: "修复中",
    active: "执行中",
    idle: "空闲",
    notLoaded: "未加载",
    inProgress: "执行中",
    interrupted: "已中断",
    "awaiting-user": "等待接受",
    cancelled: "已取消",
    completed: "已完成",
    succeeded: "已完成",
    failed: "失败",
    blocked: "受阻",
    waiting_user: "等待确认",
    accepted: "已接受",
    open: "待处理",
    resolved: "已处理",
  };

  function text(value, fallback = "未知") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }

  function clear(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
  }

  function add(parent, tag, value, className) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined && value !== null) node.textContent = text(value, "");
    parent.appendChild(node);
    return node;
  }

  function jsonText(value) {
    if (value === undefined || value === null) return "未知";
    try {
      return JSON.stringify(value, null, 2);
    } catch (_error) {
      return "无法显示此内容";
    }
  }

  function jsonBlock(parent, value) {
    const details = add(parent, "details", undefined, "technical-details");
    add(details, "summary", "技术详情 · JSON");
    const node = add(details, "pre", jsonText(value), "json-block");
    return node;
  }

  function pathLine(parent, label, value) {
    if (!value) return;
    const row = add(parent, "div", undefined, "path-row");
    add(row, "span", `${label}：`, "muted");
    add(row, "code", String(value), "path-value");
    const button = add(row, "button", "复制", "quiet-button");
    button.type = "button";
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(String(value));
        button.textContent = "已复制";
        window.setTimeout(() => { button.textContent = "复制"; }, 1200);
      } catch (_error) {
        button.textContent = "请手动选择";
      }
    });
  }

  function entityData(entity) {
    if (!entity || typeof entity !== "object") return {};
    if (entity.data && typeof entity.data === "object") return entity.data;
    return entity;
  }

  function entityId(entity) {
    if (!entity || typeof entity !== "object") return "";
    const value = entity.id ?? (entity.data && entity.data.id);
    return value === undefined || value === null ? "" : String(value);
  }

  function statusValue(entity) {
    const data = entityData(entity);
    return String(data.status ?? entity.status ?? "unknown");
  }

  function statusLabel(value) {
    const key = String((value && typeof value === "object" ? value.type : value) || "unknown");
    return statusLabels[key] || `未知状态 · ${key}`;
  }

  function statusTone(value) {
    const key = String(value || "unknown").toLowerCase();
    if (["completed", "succeeded", "accepted", "resolved"].includes(key)) return "ok";
    if (["failed", "blocked", "cancelled", "cancelling"].includes(key)) return "danger";
    if (["paused", "pending", "waiting_user", "open", "unknown"].includes(key)) return "warn";
    if (["running", "approved", "ready", "created"].includes(key)) return "accent";
    return "muted";
  }

  function statusBadge(parent, value) {
    const node = add(parent, "span", statusLabel(value), "status");
    node.dataset.tone = statusTone(value);
    return node;
  }

  function setInline(node, value, tone = "") {
    node.textContent = value || "";
    if (tone) node.dataset.tone = tone;
    else node.removeAttribute("data-tone");
  }

  function setConnection(value, tone) {
    el.connection.textContent = value;
    el.connection.dataset.tone = tone;
  }

  function formatTime(value) {
    if (!value) return "时间未知";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return text(value, "时间未知");
    return date.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
  }

  function errorMessage(error) {
    return error && error.message ? error.message : "请求失败";
  }

  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    const fetchOptions = { ...options, headers, credentials: "same-origin" };
    delete fetchOptions.bodyObj;
    if (options.bodyObj !== undefined) {
      headers.set("Content-Type", "application/json; charset=utf-8");
      fetchOptions.body = JSON.stringify(options.bodyObj);
    }
    if (String(options.method || "GET").toUpperCase() === "POST") {
      headers.set("X-Team-Token", token);
    }
    const response = await fetch(path, fetchOptions);
    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      throw new Error(`服务返回了无效响应（HTTP ${response.status}）`);
    }
    if (!response.ok || payload.ok === false) {
      const detail = payload.error && payload.error.message ? payload.error.message : payload.message;
      throw new Error(detail || `请求失败（HTTP ${response.status}）`);
    }
    return payload.data === undefined ? payload : payload.data;
  }

  function plans() {
    return state.snapshot && Array.isArray(state.snapshot.plans) ? state.snapshot.plans : [];
  }

  function runs() {
    return state.snapshot && Array.isArray(state.snapshot.runs) ? state.snapshot.runs : [];
  }

  function selectedPlan() {
    return plans().find((item) => entityId(item) === state.selectedPlanId) || null;
  }

  function selectedRun() {
    return runs().find((item) => entityId(item) === state.selectedRunId) || null;
  }

  function selectDefaults() {
    if (!plans().some((item) => entityId(item) === state.selectedPlanId)) {
      state.selectedPlanId = plans().length ? entityId(plans()[0]) : null;
    }
    if (!runs().some((item) => entityId(item) === state.selectedRunId)) {
      state.selectedRunId = runs().length ? entityId(runs()[0]) : null;
    }
  }

  async function loadSnapshot() {
    if (state.loading) return;
    state.loading = true;
    try {
      const snapshot = await request("/api/snapshot");
      state.snapshot = snapshot && typeof snapshot === "object" ? snapshot : {};
      selectDefaults();
      render();
      setConnection("已连接", "ok");
      await refreshRunFacts();
    } catch (error) {
      setConnection("连接失败", "error");
      el.snapshotTime.textContent = errorMessage(error);
    } finally {
      state.loading = false;
    }
  }

  async function refreshRunFacts() {
    const runId = state.selectedRunId;
    if (!runId) return;
    try {
      const detail = await request(`/api/snapshot?run_id=${encodeURIComponent(runId)}`);
      if (state.selectedRunId !== runId || !state.snapshot) return;
      state.snapshot.events = Array.isArray(detail.events) ? detail.events : [];
      if (Array.isArray(detail.requests)) state.snapshot.requests = detail.requests;
      if (Array.isArray(detail.notes)) state.snapshot.notes = detail.notes;
      render();
    } catch (error) {
      showRunError(`读取运行事实失败：${errorMessage(error)}`);
    }
  }

  function linkedRun(plan) {
    const ids = new Set([entityId(plan)]);
    let changed = true;
    while (changed) {
      changed = false;
      plans().forEach(candidate => {
        if (ids.has(entityData(candidate).predecessor_plan_id) && !ids.has(entityId(candidate))) {
          ids.add(entityId(candidate)); changed = true;
        }
      });
    }
    return runs().find(run => ids.has(entityData(run).plan_id)) || null;
  }
  function planDisplayStatus(plan) {
    const run = linkedRun(plan);
    return run ? (["completed", "succeeded"].includes(statusValue(run)) ? "completed" : "authorized") : statusValue(plan);
  }
  async function locateRun(runId) {
    state.selectedRunId = runId;
    render();
    await refreshRunFacts();
    const panel = document.querySelector(".runs-panel");
    panel.scrollIntoView({behavior: "smooth", block: "start"});
    el.runDetail.setAttribute("tabindex", "-1");
    el.runDetail.focus({preventScroll: true});
  }

  function renderPlans() {
    clear(el.plans);
    const items = plans();
    if (!items.length) {
      add(el.plans, "p", "还没有方案。提交 Brief 后，方案会出现在这里。", "empty-state");
      return;
    }
    items.forEach((item) => {
      const data = entityData(item);
      const id = entityId(item);
      const button = add(el.plans, "button", undefined, "list-card");
      button.type = "button";
      if (id === state.selectedPlanId) button.classList.add("selected");
      button.addEventListener("click", () => {
        state.selectedPlanId = id;
        render();
      });
      const main = add(button, "div", undefined, "card-main");
      add(main, "p", shortTitle(data, id), "card-title");
      add(main, "p", `${text(data.repository, "仓库未知")} · ${formatTime(item.updated_at || data.updated_at)}`, "card-subtitle");
      statusBadge(button, planDisplayStatus(item));
    });
  }

  function renderQuestionSection(parent, plan, data) {
    const questions = Array.isArray(data.questions) ? data.questions : [];
    if (!questions.length) return;
    const section = add(parent, "div", undefined, "subsection");
    const heading = add(section, "div", undefined, "subsection-heading");
    add(heading, "h3", "需要澄清", undefined);
    add(heading, "span", `${questions.length} 项`, undefined);
    const planId = entityId(plan);
    if (!state.answers[planId]) {
      state.answers[planId] = data.answers && typeof data.answers === "object" ? { ...data.answers } : Object.create(null);
    }
    questions.forEach((question, index) => {
      const value = typeof question === "string" ? question : question || {};
      const key = typeof question === "object" && question.id ? String(question.id) : String(index + 1);
      const prompt = typeof value === "string" ? value : value.question || value.prompt || value.text || value.label || `问题 ${index + 1}`;
      const wrap = add(section, "div", undefined, "question");
      const label = add(wrap, "label", prompt, undefined);
      const input = document.createElement("textarea");
      input.rows = 2;
      input.name = `answer-${key}`;
      input.setAttribute("aria-label", prompt);
      input.placeholder = "填写回答（可留空）";
      input.value = state.answers[planId][key] || "";
      input.addEventListener("input", () => {
        state.answers[planId][key] = input.value;
      });
      wrap.appendChild(input);
      if (typeof value === "object" && value.required === true) add(wrap, "small", "需要回答", undefined);
      label.htmlFor = input.name;
    });
    const button = add(section, "button", "带回答重新生成", "quiet-button");
    button.type = "button";
    button.addEventListener("click", () => submitProposal(plan, state.answers[planId]));
  }

  async function approvePlan(plan, startAfter) {
    const id = entityId(plan);
    const data = entityData(plan);
    const digest = data.digest || plan.digest;
    if (!id || !digest) return;
    const existing = linkedRun(plan);
    if (existing) { await locateRun(entityId(existing)); return; }
    try {
      setInline(el.proposeStatus, startAfter ? "正在授权并启动…" : "正在授权…");
      const result = await request(`/api/plans/${encodeURIComponent(id)}/approve`, {
        method: "POST",
        bodyObj: { expected_digest: digest },
      });
      const runId = entityId(result);
      if (startAfter && runId) await request(`/api/runs/${encodeURIComponent(runId)}/start`, { method: "POST", bodyObj: {} });
      state.selectedRunId = runId || state.selectedRunId;
      setInline(el.proposeStatus, startAfter ? "已授权并启动" : "已授权", "ok");
      await loadSnapshot();
      if (runId) await locateRun(runId);
    } catch (error) {
      setInline(el.proposeStatus, errorMessage(error), "error");
    }
  }

  function renderPlanDetail() {
    clear(el.planDetail);
    const plan = selectedPlan();
    if (!plan) {
      el.planDetail.className = "detail empty-state";
      add(el.planDetail, "span", "选择一个方案查看详情。", undefined);
      return;
    }
    el.planDetail.className = "detail";
    const data = entityData(plan);
    const header = add(el.planDetail, "div", undefined, "detail-header");
    const heading = add(header, "div", undefined, "card-main");
    add(heading, "h3", shortTitle(data, entityId(plan)), "detail-title");
    add(heading, "div", `${text(data.repository, "仓库未知")} · ${formatTime(plan.updated_at || data.updated_at)}`, "detail-meta");
    statusBadge(header, planDisplayStatus(plan));

    const actionRow = add(el.planDetail, "div", undefined, "button-row");
    const digest = data.digest || plan.digest;
    const existing = linkedRun(plan);
    const canApprove = !existing && Boolean(digest) && statusValue(plan) === "ready";
    if (existing) {
      const locate = add(actionRow, "button", "查看关联运行", "primary");
      locate.type = "button";
      locate.addEventListener("click", () => locateRun(entityId(existing)));
      add(actionRow, "span", `当前状态：${statusLabel(statusValue(existing))}`, "muted");
    }
    if (!existing) {
    const approve = add(actionRow, "button", "授权", "primary");
    approve.type = "button";
    approve.disabled = !canApprove;
    approve.title = canApprove ? "冻结当前方案并创建运行" : "当前方案不可授权或缺少 digest";
    approve.addEventListener("click", () => approvePlan(plan, false));
    const approveStart = add(actionRow, "button", "授权并启动", "primary");
    approveStart.type = "button";
    approveStart.disabled = !canApprove;
    approveStart.addEventListener("click", () => approvePlan(plan, true));
    }

    renderQuestionSection(el.planDetail, plan, data);
    if (data.brief) {
      const brief = add(el.planDetail, "details", undefined, "brief-details");
      add(brief, "summary", "查看完整 Brief");
      add(brief, "p", data.brief, "long-text");
    }
    const body = add(el.planDetail, "details", undefined, "proposal-details");
    add(body, "summary", "展开方案 · 目标、分工与验收");
    renderProposal(body, data);

    const proposal = add(body, "div", undefined, "subsection");
    add(proposal, "div", "方案内容", "subsection-heading");
    jsonBlock(proposal, data.proposal === undefined ? data : data.proposal);
    const digestSection = add(body, "div", undefined, "subsection");
    add(digestSection, "div", "方案 digest", "muted");
    add(digestSection, "code", digest || "尚未生成", "digest");
  }

  function renderRuns() {
    clear(el.runs);
    const items = runs();
    if (!items.length) {
      add(el.runs, "p", "授权方案后，运行会出现在这里。", "empty-state");
      return;
    }
    items.forEach((item) => {
      const data = entityData(item);
      const id = entityId(item);
      const button = add(el.runs, "button", undefined, "list-card");
      button.type = "button";
      if (id === state.selectedRunId) button.classList.add("selected");
      button.addEventListener("click", () => {
        state.selectedRunId = id;
        render();
        refreshRunFacts();
      });
      const main = add(button, "div", undefined, "card-main");
      add(main, "p", shortTitle(data.plan || data, id), "card-title");
      add(main, "p", `方案 ${text(data.plan_id, "未知")} · ${formatTime(data.created_at || item.updated_at)}`, "card-subtitle");
      statusBadge(button, statusValue(item));
    });
  }

  function runActionButton(parent, run, action, label, className = "") {
    const button = add(parent, "button", label, className);
    button.type = "button";
    const allowed = {start: ["authorized"], pause: ["running", "verifying"], resume: ["paused", "blocked"], cancel: ["authorized", "running", "verifying", "paused", "blocked", "pause-requested", "awaiting-user"]};
    button.disabled = !(allowed[action] || []).includes(statusValue(run));
    button.title = button.disabled ? "当前状态不支持此操作" : label;
    button.addEventListener("click", async () => {
      const id = entityId(run);
      try {
        button.disabled = true;
        setConnection(`${label}…`, "muted");
        await request(`/api/runs/${encodeURIComponent(id)}/${action}`, { method: "POST", bodyObj: {} });
        await loadSnapshot();
      } catch (error) {
        showRunError(errorMessage(error));
      } finally {
        button.disabled = false;
      }
    });
    return button;
  }

  function showRunError(message) {
    const current = el.runDetail.querySelector(".error-box");
    if (current) current.textContent = message;
    else el.runDetail.prepend(add(document.createElement("div"), "div", message, "error-box"));
  }

  function packagesFor(data) {
    let runtime;
    if (Array.isArray(data.packages)) runtime = data.packages;
    else if (data.packages && typeof data.packages === "object") {
      runtime = Object.entries(data.packages).map(([id, value]) => ({
        ...(value && typeof value === "object" ? value : {}),
        id,
      }));
    }
    runtime = runtime || [];
    const definitions = data.plan && data.plan.proposal && Array.isArray(data.plan.proposal.work_packages)
      ? data.plan.proposal.work_packages : [];
    if (!definitions.length) return runtime;
    const byId = new Map(runtime.map((item, index) => [packageId(item, index), item]));
    return definitions.map((definition) => ({
      ...(definition && typeof definition === "object" ? definition : {}),
      ...(byId.get(packageId(definition, 0)) || {}),
      id: packageId(definition, 0),
    }));
  }

  function packageId(item, index) {
    if (typeof item === "string") return item;
    return text(item && (item.id || item.package_id || item.name), `package-${index + 1}`);
  }

  function renderSteerForm(parent, run, packageValue) {
    const form = add(parent, "form", undefined, "resolve-form");
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "给这个工作包的纠偏说明";
    input.maxLength = 200000;
    input.required = true;
    form.appendChild(input);
    const button = add(form, "button", "发送纠偏", "quiet-button");
    button.type = "submit";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!input.value.trim()) return;
      try {
        button.disabled = true;
        await request(`/api/runs/${encodeURIComponent(entityId(run))}/steer`, {
          method: "POST",
          bodyObj: { package_id: packageValue, message: input.value.trim() },
        });
        input.value = "";
        await loadSnapshot();
      } catch (error) {
        showRunError(errorMessage(error));
      } finally {
        button.disabled = false;
      }
    });
  }

  function renderPackages(parent, run, data) {
    const items = packagesFor(data);
    const section = add(parent, "div", undefined, "subsection");
    const heading = add(section, "div", undefined, "subsection-heading");
    add(heading, "h3", "工作包", undefined);
    add(heading, "span", `${items.length} 个`, undefined);
    if (!items.length) {
      add(section, "p", "当前没有可显示的工作包。", "muted");
      return;
    }
    const list = add(section, "div", undefined, "package-list");
    items.forEach((item, index) => {
      const value = typeof item === "string" ? { id: item } : item || {};
      const id = packageId(item, index);
      const card = add(list, "div", undefined, "package");
      const head = add(card, "div", undefined, "package-head");
      add(head, "strong", id, undefined);
      statusBadge(head, value.status || "unknown");
      if (value.thread_id) pathLine(card, "会话", value.thread_id);
      add(card, "p", value.model ? `服务报告配置：${value.model} · ${value.reasoning || "思考程度未确认"}` : "执行配置尚未确认", "muted");
      const path = value.workspace || value.workspace_path || value.path || value.repository;
      pathLine(card, "工作区", path);
      if (value.goal || value.title) add(card, "p", value.goal || value.title, undefined);
      if (Array.isArray(value.write_paths) && value.write_paths.length) pathLine(card, "写入范围", value.write_paths.join(", "));
      if (value.evidence !== undefined) {
        add(card, "p", "证据", undefined);
        if (Array.isArray(value.evidence)) value.evidence.forEach((ref) => pathLine(card, "证据路径", ref && ref.path));
        else if (value.evidence && typeof value.evidence === "object") pathLine(card, "证据路径", value.evidence.path);
        jsonBlock(card, value.evidence);
      }
      if (value.error && !["completed", "succeeded", "accepted"].includes(value.status)) add(card, "p", value.error, "error-box");
      const packageStatus = String(value.status || "").toLowerCase();
      if (["running", "active", "executing", "in_progress"].includes(packageStatus)) {
        renderSteerForm(card, run, id);
      }
    });
  }

  function allRequests(run, data) {
    const source = state.snapshot && Array.isArray(state.snapshot.requests) ? state.snapshot.requests : [];
    const local = Array.isArray(data.requests) ? data.requests : [];
    const values = source.length ? source : local;
    const runId = entityId(run);
    return values.filter((item) => {
      const value = entityData(item);
      return !value.run_id && !item.run_id || String(value.run_id || item.run_id) === runId;
    });
  }

  function requestId(item, index) {
    return text(item && (item.id || item.request_id || (item.data && (item.data.id || item.data.request_id))), `request-${index + 1}`);
  }

  function renderRequests(parent, run, data) {
    const items = allRequests(run, data);
    if (packagesFor(data).length < 2 && !items.length) return;
    const section = add(parent, "div", undefined, "subsection");
    const heading = add(section, "div", undefined, "subsection-heading");
    add(heading, "h3", "协作请求", undefined);
    add(heading, "span", `${items.length} 项`, undefined);
    if (!items.length) {
      add(section, "p", "当前没有协作请求。", "muted");
    } else {
      const list = add(section, "div", undefined, "request-list");
      items.forEach((item, index) => {
        const value = entityData(item);
        const card = add(list, "div", undefined, "request");
        const head = add(card, "div", undefined, "request-head");
        add(head, "strong", requestId(item, index), undefined);
        statusBadge(head, value.status || item.status || "unknown");
        add(card, "p", `${text(value.from_package, "未知来源")} → ${text(value.to_package, "未知目标")}`, undefined);
        add(card, "p", text(value.question, "问题未知"), undefined);
        if (value.answer) add(card, "p", `回答：${value.answer}`, undefined);
        const requestStatus = String(value.status || item.status || "").toLowerCase();
        if (!["resolved", "accepted", "completed"].includes(requestStatus)) {
          const form = add(card, "form", undefined, "resolve-form");
          const input = document.createElement("textarea");
          input.rows = 2;
          input.placeholder = "填写处理结果";
          input.required = true;
          form.appendChild(input);
          const button = add(form, "button", "提交回答", "quiet-button");
          button.type = "submit";
          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!input.value.trim()) return;
            try {
              button.disabled = true;
              await request(`/api/runs/${encodeURIComponent(entityId(run))}/requests/${encodeURIComponent(requestId(item, index))}/resolve`, {
                method: "POST",
                bodyObj: { answer: input.value.trim() },
              });
              await loadSnapshot();
            } catch (error) {
              showRunError(errorMessage(error));
            } finally {
              button.disabled = false;
            }
          });
        }
      });
    }
    return section;
  }

  function renderCollaborationForm(parent, run, data) {
    const items = packagesFor(data);
    if (items.length < 2 || !["running", "paused", "blocked"].includes(statusValue(run))) return;
    const section = add(parent, "div", undefined, "subsection");
    const heading = add(section, "div", undefined, "subsection-heading");
    add(heading, "h3", "发起协作请求", undefined);
    add(heading, "span", "需要另一个工作包的输入时使用", undefined);
    const form = add(section, "form", undefined, "stack");
    const row = add(form, "div", undefined, "two-col");
    const fromLabel = add(row, "label", "发起包", undefined);
    const from = document.createElement(items.length ? "select" : "input");
    from.required = true;
    if (!items.length) from.placeholder = "工作包 ID";
    else items.forEach((item, index) => {
      const option = document.createElement("option");
      option.value = packageId(item, index);
      option.textContent = option.value;
      from.appendChild(option);
    });
    row.appendChild(from);
    fromLabel.htmlFor = from.id = `from-package-${entityId(run)}`;
    const toLabel = add(row, "label", "目标包", undefined);
    const to = document.createElement(items.length ? "select" : "input");
    to.required = true;
    if (!items.length) to.placeholder = "工作包 ID";
    else items.forEach((item, index) => {
      const option = document.createElement("option");
      option.value = packageId(item, index);
      option.textContent = option.value;
      to.appendChild(option);
    });
    row.appendChild(to);
    toLabel.htmlFor = to.id = `to-package-${entityId(run)}`;
    to.selectedIndex = 1;
    const syncTarget = () => {
      Array.from(to.options).forEach(option => { option.disabled = option.value === from.value; });
      if (to.value === from.value) to.value = Array.from(to.options).find(option => !option.disabled).value;
    };
    from.addEventListener("change", syncTarget);
    syncTarget();
    const question = document.createElement("textarea");
    question.rows = 2;
    question.placeholder = "需要对方回答的问题";
    question.required = true;
    form.appendChild(question);
    const button = add(form, "button", "发送协作请求", "quiet-button");
    button.type = "submit";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        button.disabled = true;
        await request(`/api/runs/${encodeURIComponent(entityId(run))}/collaboration`, {
          method: "POST",
          bodyObj: { from_package: from.value.trim(), to_package: to.value.trim(), question: question.value.trim() },
        });
        question.value = "";
        await loadSnapshot();
      } catch (error) {
        showRunError(errorMessage(error));
      } finally {
        button.disabled = false;
      }
    });
  }

  function renderCheckpoint(parent, run, data) {
    const checkpoint = data.checkpoint;
    const checkpointDigest = data.checkpoint_digest;
    if ((checkpoint === undefined || checkpoint === null) && !checkpointDigest) return;
    const value = typeof checkpoint === "object" && checkpoint !== null ? { ...checkpoint } : { value: checkpoint };
    if (checkpointDigest && !value.digest) value.digest = checkpointDigest;
    if (!value.status && statusValue(run) === "completed") value.status = "accepted";
    const section = add(parent, "div", undefined, "subsection");
    const heading = add(section, "div", undefined, "subsection-heading");
    add(heading, "h3", "检查点", undefined);
    statusBadge(heading, value.status || "waiting_user");
    const digest = value.digest || value.expected_digest;
    if (value.evidence !== undefined) {
      add(section, "p", "当前证据", "muted");
      if (Array.isArray(value.evidence)) value.evidence.forEach((ref) => pathLine(section, "证据路径", ref && ref.path));
      else if (value.evidence && typeof value.evidence === "object") pathLine(section, "证据路径", value.evidence.path);
      jsonBlock(section, value.evidence);
    }
    if (digest) {
      add(section, "code", digest, "digest");
      const accepted = ["accepted", "completed"].includes(String(value.status || "").toLowerCase());
      const button = add(section, "button", accepted ? "检查点已接受" : "接受当前检查点", accepted ? "quiet-button" : "primary");
      button.type = "button";
      button.disabled = accepted || statusValue(run) !== "awaiting-user";
      button.addEventListener("click", async () => {
        try {
          button.disabled = true;
          await request(`/api/runs/${encodeURIComponent(entityId(run))}/checkpoint/accept`, {
            method: "POST",
            bodyObj: { expected_digest: digest },
          });
          await loadSnapshot();
        } catch (error) {
          button.disabled = false;
          showRunError(errorMessage(error));
        }
      });
    } else {
      add(section, "p", "当前没有可接受的证据 digest。", "muted");
    }
  }

  function renderEvents(parent, run) {
    const runId = entityId(run);
    const events = state.snapshot && Array.isArray(state.snapshot.events) ? state.snapshot.events : [];
    const items = events.filter((item) => {
      const payload = item && item.payload && typeof item.payload === "object" ? item.payload : {};
      return String(item.run_id || (item.data && item.data.run_id) || payload.run_id || "") === runId;
    });
    const section = add(parent, "div", undefined, "subsection");
    const heading = add(section, "div", undefined, "subsection-heading");
    add(heading, "h3", "事件与证据", undefined);
    add(heading, "span", `${items.length} 条`, undefined);
    if (!items.length) {
      add(section, "p", "还没有可显示的事件。", "muted");
      return;
    }
    const controls = add(section, "div", undefined, "button-row");
    const toggle = add(controls, "button", "查看全部事件", "quiet-button"); toggle.type = "button";
    const history = add(controls, "button", "搜索历史", "quiet-button"); history.type = "button";
    history.addEventListener("click", () => {
      const search = el.runDetail.querySelector(".history-search");
      if (search) { search.open = true; search.scrollIntoView({behavior: "smooth", block: "center"}); search.querySelector("input").focus({preventScroll: true}); }
    });
    const note = add(section, "p", "", "muted");
    const list = add(section, "div", undefined, "event-list");
    let all = false;
    const draw = () => {
      clear(list);
      const keyItems = items.filter(item => !["usage", "activity", "planning-usage"].includes(item.type));
      const shown = (all ? items : keyItems.slice(-20)).slice().reverse();
      note.textContent = all ? `全部 ${items.length} 条事件（当前快照）` : `最近 ${shown.length} 条关键事件 · 隐藏例行用量与活动记录`;
      toggle.textContent = all ? "仅看关键事件" : "查看全部事件";
      shown.forEach(item => {
        const card = add(list, "div", undefined, "event");
        const head = add(card, "div", undefined, "event-head");
        add(head, "strong", eventLabel(item.type || item.event_type));
        add(head, "span", `#${text(item.seq, "?")} · ${formatTime(item.created_at)}`);
        add(card, "p", eventSummary(item), "long-text");
        jsonBlock(card, item.payload === undefined ? item : item.payload);
      });
    };
    toggle.addEventListener("click", () => { all = !all; draw(); });
    draw();
  }

  function eventLabel(type) {
    const labels = {
      authorized: "方案已授权", "authorization-amended": "运行预算已修改", "new-project-created": "项目已创建",
      "toolchain-qualified": "工具检查通过", "session-bound": "执行会话已连接", "session-replaced": "执行会话已替换",
      "native-project-bound": "原生项目已登记", "native-project-verified": "原生项目已核对",
      "direction-review-started": "开始方向审查", "direction-reviewed": "方向审查完成", "direction-review-stopped": "方向审查停止",
      "responsibility-transferred": "责任交接已准备", "handoff-verified": "接管依据已核对", reconciled: "运行现场已核对",
      "material-observed": "源码变化已观测", "turn/started": "执行回合开始", "turn/completed": "执行回合结束",
      "thread/status/changed": "原生会话状态变化", "toolchain-requalified": "更新后的工具已核验", "runtime-cache-cleaned": "运行缓存已清理",
      "reattached-active-turn": "已重新连接执行", "package-completed": "工作包已完成", "package-blocked": "工作包受阻",
      "material-progress": "工作进展", "reallocation-proposed": "分工调整建议", "input-required": "需要输入",
      "bounded-repair-started": "开始修复", "repair-attempt-finished": "修复尝试结束", "gate-started": "开始验收检查",
      "gate-completed": "验收检查结束", "checkpoint-reached": "已到达检查点", "checkpoint-accepted": "检查点已接受",
      "pause-requested": "已请求暂停", "cancel-requested": "已请求取消", "resume-requested": "已请求恢复",
      "run-blocked": "运行受阻", "run-paused": "运行已暂停", "run-cancelled": "运行已取消", paused: "已暂停", cancelled: "已取消",
      "correction-queued": "纠正指令已排队", "correction-delivered": "纠正指令已送达", "interrupt-requested": "已请求中断",
      "collaboration-requested": "协作请求已发送", "collaboration-completed": "协作已完成", "subagent-call": "子代理协作",
      usage: "用量记录", activity: "执行活动", work_note: "工作笔记已更新"
    };
    return labels[type] || "运行事件";
  }
  function eventSummary(item) {
    const p = item.payload || {};
    const scope = p.package || p.package_id || p.gate || "";
    let summary = p.message || p.error || p.current_goal || p.question || p.proposal;
    if (!summary && item.type === "gate-completed") summary = p.passed ? "检查通过" : `检查未通过，退出码 ${p.exit_code}`;
    if (!summary && item.type === "gate-started") summary = Array.isArray(p.argv) ? p.argv.join(" ") : "正在执行验收命令";
    if (!summary && item.type === "package-completed") summary = "工作成果与证据已记录";
    if (!summary && item.type === "session-bound") summary = "工作包已连接到执行会话";
    if (!summary && item.type === "usage") summary = "记录本轮模型用量，展开技术详情查看";
    if (!summary) summary = p.status ? statusLabel(p.status) : eventLabel(item.type);
    const value = typeof summary === "string" ? summary : jsonText(summary);
    return `${scope ? scope + " · " : ""}${value.length > 220 ? value.slice(0,220) + "…" : value}`;
  }

  function renderRunDetail() {
    clear(el.runDetail);
    const run = selectedRun();
    if (!run) {
      el.runDetail.className = "detail empty-state";
      add(el.runDetail, "span", "选择一个运行查看工作包、请求和检查点。", undefined);
      return;
    }
    el.runDetail.className = "detail";
    const data = entityData(run);
    const header = add(el.runDetail, "div", undefined, "detail-header");
    const heading = add(header, "div", undefined, "card-main");
    add(heading, "h3", shortTitle(data.plan || data, entityId(run)), "detail-title");
    add(heading, "div", `方案 ${text(data.plan_id, "未知")} · 创建于 ${formatTime(data.created_at || run.updated_at)}`, "detail-meta");
    statusBadge(header, statusValue(run));
    if (data.observation_state === "stale") add(el.runDetail, "p", "运行记录已过期，不能据此判断执行仍在继续。请核对原生会话后恢复。", "error-box");
    if (data.native_project_id) pathLine(el.runDetail, "原生项目", data.native_project_id);
    const actions = add(el.runDetail, "div", undefined, "button-row");
    runActionButton(actions, run, "start", "启动", "primary");
    runActionButton(actions, run, "pause", "暂停");
    runActionButton(actions, run, "resume", "恢复");
    runActionButton(actions, run, "cancel", "取消", "danger");

    const limits = data.limits;
    if (limits !== undefined) {
      const section = add(el.runDetail, "div", undefined, "subsection");
      add(section, "h3", "运行限制", undefined);
      renderPolicySummary(section, limits);
      if (data.usage_by_thread) {
        const observed = Object.values(data.usage_by_thread).reduce((sum, value) => sum + (Number(value) || 0), 0);
        add(section, "p", `已观测 Token：${observed.toLocaleString("zh-CN")}（含缓存输入，不等同费用）`, "muted");
      }
      renderLimitsForm(section, run, data);
    }
    if (data.stop_intent && !["paused", "cancelled"].includes(data.status)) add(el.runDetail, "p", data.stop_intent === "pause" ? "已请求暂停，正在等待当前执行确认停止。" : "已请求取消，正在等待当前执行确认停止。", "muted");
    if (data.error) showRunError(typeof data.error === "string" ? data.error : jsonText(data.error));
    renderPackages(el.runDetail, run, data);
    renderNotesAndHistory(el.runDetail, run, data);
    renderCollaborationForm(el.runDetail, run, data);
    renderRequests(el.runDetail, run, data);
    renderCheckpoint(el.runDetail, run, data);
    if (Array.isArray(data.evidence) && data.evidence.length) {
      const evidence = add(el.runDetail, "div", undefined, "subsection");
      add(evidence, "h3", "运行证据", undefined);
      data.evidence.forEach((ref) => pathLine(evidence, "证据路径", ref && ref.path));
      jsonBlock(evidence, data.evidence);
    }
    renderEvents(el.runDetail, run);
  }

  function render() {
    renderPlans();
    renderPlanDetail();
    renderRuns();
    renderRunDetail();
    if (state.snapshot && state.snapshot.updated_at) el.snapshotTime.textContent = `读取于 ${formatTime(state.snapshot.updated_at)}`;
    else el.snapshotTime.textContent = `读取于 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }

  function wait(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  async function pollJob(jobId) {
    for (;;) {
      try {
        const job = await request(`/api/jobs/${encodeURIComponent(jobId)}`);
        const status = String(job.status || "unknown");
        if (status === "queued" || status === "running") {
          setInline(el.proposeStatus, `方案生成${statusLabel(status)}…`);
          await wait(800);
          continue;
        }
        if (status === "failed") {
          const detail = job.error && job.error.message ? job.error.message : "方案生成失败";
          setInline(el.proposeStatus, detail, "error");
          return;
        }
        if (status === "succeeded") {
          const result = job.result;
          const id = entityId(result);
          if (id) state.selectedPlanId = id;
          setInline(el.proposeStatus, "方案已生成", "ok");
          await loadSnapshot();
          return;
        }
        setInline(el.proposeStatus, `方案生成状态：${statusLabel(status)}`);
        return;
      } catch (error) {
        setInline(el.proposeStatus, errorMessage(error), "error");
        return;
      }
    }
  }

  async function submitProposal(plan, answers) {
    const data = plan ? entityData(plan) : {};
    const repository = plan ? data.repository : el.repository.value.trim();
    const brief = plan ? data.brief : el.brief.value.trim();
    if (!repository || !brief) {
      setInline(el.proposeStatus, "请填写仓库路径和 Brief", "error");
      return;
    }
    try {
      setInline(el.proposeStatus, "已提交，等待 Engine…");
      const result = await request("/api/propose", {
        method: "POST",
        bodyObj: { repository, brief, answers: answers || undefined, policy: plan ? data.policy : readPolicy(el.briefForm) },
      });
      const job = result.job || result;
      state.jobId = job.id || result.job_id;
      if (!state.jobId) throw new Error("服务没有返回 proposal job id");
      await pollJob(state.jobId);
    } catch (error) {
      setInline(el.proposeStatus, errorMessage(error), "error");
    }
  }



  function shortTitle(data, fallback) {
    const source = text(data.title || data.name || (data.proposal && data.proposal.objective) || data.brief, fallback);
    const line = source.split(/[\r\n]/)[0].replace(/^#+\s*/, "");
    return line.length > 42 ? line.slice(0, 42) + "…" : line;
  }

  const policyFields = [
    ["model", "模型", "gpt-5.6-luna"], ["reasoning", "推理强度", "max"],
    ["max_sessions", "最大会话数", 2], ["max_subagents_per_session", "每会话子代理上限", 1],
    ["max_turn_seconds", "单轮时限（秒）", 1200], ["max_run_seconds", "运行时限（秒）", 3600],
    ["max_repair_attempts", "修复次数上限", 2], ["token_budget", "Token 预算", 200000],
    ["network_access", "允许网络访问", false],
  ];
  function renderPolicyInputs(parent, values = {}, resourcesOnly = false) {
    policyFields.filter(([key]) => !resourcesOnly || key.startsWith("max_") || key === "token_budget").forEach(([key, label, fallback]) => {
      const field = add(parent, "label", label, "policy-field");
      const input = add(field, "input");
      input.name = key;
      input.type = typeof fallback === "boolean" ? "checkbox" : typeof fallback === "number" ? "number" : "text";
      if (input.type === "checkbox") input.checked = values[key] ?? fallback;
      else { input.value = values[key] ?? fallback; input.required = true; }
      if (input.type === "number") { input.step = "1"; input.min = ["max_subagents_per_session", "max_repair_attempts"].includes(key) ? "0" : "1"; }
    });
  }
  function readPolicy(parent) {
    return Object.fromEntries(policyFields.filter(([key]) => parent.querySelector(`[name="${key}"]`)).map(([key,,fallback]) => {
      const input = parent.querySelector(`[name="${key}"]`);
      return [key, typeof fallback === "boolean" ? input.checked : typeof fallback === "number" ? Number(input.value) : input.value.trim()];
    }));
  }
  function renderPolicySummary(parent, policy = {}) {
    const grid = add(parent, "dl", undefined, "facts-grid");
    policyFields.forEach(([key,label]) => {
      if (policy[key] === undefined) return;
      const cell = add(grid, "div"); add(cell, "dt", label);
      add(cell, "dd", typeof policy[key] === "boolean" ? (policy[key] ? "允许" : "关闭") : policy[key]);
    });
  }
  function section(parent, title) {
    const node = add(parent, "section", undefined, "subsection"); add(node, "h3", title); return node;
  }
  function lines(parent, values, empty = "未提供") {
    if (!Array.isArray(values) || !values.length) { add(parent, "p", empty, "muted"); return; }
    const list = add(parent, "ul", undefined, "readable-list");
    values.forEach(value => add(list, "li", value));
  }
  function renderProposal(parent, data) {
    const p = data.proposal || {};
    add(section(parent, "目标"), "p", p.objective || "方案尚未生成", "long-text");
    const allocation = section(parent, "分工");
    add(allocation, "p", p.mode === "single-session" ? "单会话执行" : p.mode === "multi-session" ? "多会话协作" : "执行方式待定", "muted");
    if (p.allocation_reason) add(allocation, "p", p.allocation_reason, "long-text");
    (p.work_packages || []).forEach(pkg => {
      const card = add(allocation, "article", undefined, "package");
      add(card, "strong", `${pkg.id} · ${pkg.title}`); add(card, "p", pkg.goal);
      add(card, "p", `依赖：${(pkg.depends_on || []).join("、") || "无"}`);
      add(card, "p", `验收：${pkg.acceptance_notes || "未提供"}`);
    });
    const permissions = section(parent, "权限与写入边界");
    lines(permissions, (p.work_packages || []).map(pkg => `${pkg.title || pkg.id}：${(pkg.write_paths || []).join("、") || "只读，不写入仓库"}`));
    const resources = section(parent, "资源与预算");
    pathLine(resources, "仓库", data.repository); renderPolicySummary(resources, data.policy || {});
    const checkpoint = section(parent, "检查点");
    add(checkpoint, "p", p.checkpoint?.title || "未提供", "long-text");
    if (p.checkpoint) add(checkpoint, "p", p.checkpoint.requires_user_acceptance ? "需要用户接受当前证据" : "按方案检查点完成", "muted");
    lines(section(parent, "假设"), p.assumptions, "没有声明额外假设");
    const acceptance = section(parent, "验收条件");
    lines(acceptance, (p.requirements || []).map(r => `${r.text}（负责：${r.owner}；检查：${(r.gate_ids || []).join("、")}）`));
    (p.gates || []).forEach(g => {
      const card = add(acceptance, "div", undefined, "package");
      add(card, "strong", `${g.id} · ${g.description}`);
      add(card, "p", `超时：${g.timeout_seconds} 秒`);
      add(card, "code", (g.argv || []).join(" "), "path-value");
    });
  }
  function renderLimitsForm(parent, run, data) {
    if (!["paused", "blocked"].includes(statusValue(run))) return;
    const details = add(parent, "details", undefined, "brief-details");
    add(details, "summary", "修改运行预算");
    add(details, "p", "修改将单独记录。提交成功后，再点击恢复运行。", "muted");
    const form = add(details, "form", undefined, "stack");
    const fields = add(form, "div", undefined, "policy-fields");
    renderPolicyInputs(fields, data.limits || {}, true);
    const button = add(form, "button", "提交预算修改", "primary"); button.type = "submit";
    const digest = data.limits_digest || data.policy_digest;
    button.disabled = !digest;
    if (!digest) add(form, "p", "当前 Engine 暂未提供可修改的预算版本。", "muted");
    const feedback = add(form, "p", "", "inline-status");
    form.addEventListener("submit", async event => {
      event.preventDefault(); button.disabled = true;
      try {
        await request(`/api/runs/${encodeURIComponent(entityId(run))}/limits`, {method: "POST", bodyObj: {policy: readPolicy(form), expected_digest: digest}});
        await loadSnapshot();
      } catch (error) { setInline(feedback, errorMessage(error), "error"); button.disabled = false; }
    });
  }
  function renderNote(parent, raw) {
    const value = entityData(raw);
    if (!raw || !Object.keys(value).length) { add(parent, "p", "尚无工作笔记。", "muted"); return; }
    const content = value.content ?? value.note ?? value.text ?? value.summary;
    if (typeof content === "string") add(parent, "p", content, "long-text");
    else {
      Object.entries(value).forEach(([key, val]) => {
        if (["id", "run_id", "package_id", "updated_at", "created_at"].includes(key)) return;
        const labels = {current_goal: "当前目标", decisions: "已作决定", verified: "已验证", remaining: "待完成", next_action: "下一步", references: "依据引用"};
        if (labels[key]) add(parent, "strong", labels[key]);
        if (typeof val === "string") add(parent, "p", `${val}`, "long-text");
        else if (Array.isArray(val) && val.every(x => typeof x === "string")) lines(parent, val);
        else if (key === "references" && Array.isArray(val)) val.forEach(ref => add(parent, "p", ref.path || `事件 #${ref.event_seq}`, "muted"));
      });
    }
    jsonBlock(parent, raw);
  }
  function renderNotesAndHistory(parent, run, data) {
    const node = section(parent, "工作笔记与历史");
    const notes = state.snapshot?.notes;
    const items = Array.isArray(notes) ? notes.filter(note => entityData(note).run_id === entityId(run)) : [];
    if (!Array.isArray(notes)) add(node, "p", "当前快照暂未提供工作笔记，可按工作包读取。", "muted");
    packagesFor(data).forEach((pkg, index) => {
      const id = packageId(pkg, index);
      const detail = add(node, "details", undefined, "brief-details");
      add(detail, "summary", `${pkg.title || id} · 工作笔记`);
      const content = add(detail, "div");
      const note = items.find(item => entityData(item).package_id === id || entityData(item).package === id);
      if (note) renderNote(content, note);
      detail.addEventListener("toggle", async () => {
        if (!detail.open || detail.dataset.loaded) return;
        detail.dataset.loaded = "true";
        try { const result = await request(`/api/notes?run_id=${encodeURIComponent(entityId(run))}&package_id=${encodeURIComponent(id)}`); clear(content); renderNote(content, result); }
        catch (error) { add(content, "p", errorMessage(error), "muted"); }
      });
    });
    const search = add(node, "details", undefined, "brief-details history-search"); add(search, "summary", "搜索运行历史");
    const form = add(search, "form", undefined, "stack");
    const label = add(form, "label", "关键词"); const query = add(label, "input"); query.type = "search"; query.required = true; query.maxLength = 512;
    const scopeLabel = add(form, "label", "工作包范围"); const scope = add(scopeLabel, "select");
    add(scope, "option", "全部工作包").value = "";
    packagesFor(data).forEach((pkg, index) => { add(scope, "option", pkg.title || packageId(pkg,index)).value = packageId(pkg,index); });
    const button = add(form, "button", "搜索历史", "quiet-button"); button.type = "submit";
    const results = add(search, "div", undefined, "history-results");
    form.addEventListener("submit", async event => {
      event.preventDefault(); button.disabled = true; clear(results);
      try {
        const params = new URLSearchParams({run_id: entityId(run), query: query.value.trim(), limit: "20"});
        if (scope.value) params.set("package_id", scope.value);
        const response = await request(`/api/history?${params}`);
        const hits = Array.isArray(response) ? response : response.results || response.items || [];
        add(results, "p", `${hits.length} 条匹配结果（最多 20 条）`, "muted");
        hits.forEach(hit => { const card = add(results, "article", undefined, "event"); add(card, "strong", `${hit.source_kind === "note" ? "工作笔记" : "历史事件"} #${hit.seq || "?"} · ${formatTime(hit.time)}`); renderNote(card, hit); });
      } catch (error) { add(results, "p", errorMessage(error), "error-box"); }
      finally { button.disabled = false; }
    });
  }

  el.briefForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitProposal(null, null);
  });
  renderPolicyInputs(el.briefForm.querySelector(".policy-fields"));
  el.refresh.addEventListener("click", () => loadSnapshot());
  loadSnapshot();
  window.setInterval(() => {
    if (!document.hidden && !document.querySelector("details[open]") && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) loadSnapshot();
  }, 5000);
})();
