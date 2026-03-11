const state = {
  baseUrl: window.location.origin,
  gameId: null,
  humanSlots: [],
};

const els = {
  provider: document.getElementById('provider'),
  modelName: document.getElementById('modelName'),
  baseUrl: document.getElementById('baseUrl'),
  apiKey: document.getElementById('apiKey'),
  baseUrlWrap: document.getElementById('baseUrlWrap'),
  apiKeyWrap: document.getElementById('apiKeyWrap'),
  temperature: document.getElementById('temperature'),
  seed: document.getElementById('seed'),
  maxActions: document.getElementById('maxActions'),
  createGameBtn: document.getElementById('createGameBtn'),
  refreshBtn: document.getElementById('refreshBtn'),
  autoplayBtn: document.getElementById('autoplayBtn'),
  createResult: document.getElementById('createResult'),
  pendingMeta: document.getElementById('pendingMeta'),
  pendingList: document.getElementById('pendingList'),
  historyBtn: document.getElementById('historyBtn'),
  historyLog: document.getElementById('historyLog'),
  viewerSlot: document.getElementById('viewerSlot'),
  stateBtn: document.getElementById('stateBtn'),
  stateLog: document.getElementById('stateLog'),
};

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

async function api(path, options = {}) {
  const res = await fetch(`${state.baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail || data.error || res.statusText;
    throw new Error(`${res.status}: ${detail}`);
  }
  return data;
}

function toggleControls(enabled) {
  els.refreshBtn.disabled = !enabled;
  els.autoplayBtn.disabled = !enabled;
  els.historyBtn.disabled = !enabled;
  els.stateBtn.disabled = !enabled;
}

function renderViewerSlots() {
  els.viewerSlot.innerHTML = '';
  state.humanSlots.forEach((slot) => {
    const opt = document.createElement('option');
    opt.value = String(slot);
    opt.textContent = `槽位 ${slot}`;
    els.viewerSlot.appendChild(opt);
  });
}

function updateProviderHints() {
  const provider = els.provider.value;
  const showConnectionInputs = provider !== 'mock';
  els.baseUrlWrap.style.display = showConnectionInputs ? 'flex' : 'none';
  els.apiKeyWrap.style.display = showConnectionInputs ? 'flex' : 'none';

  if (provider === 'openai') {
    els.modelName.value = els.modelName.value || 'gpt-4.1-mini';
    if (!els.baseUrl.value) {
      els.baseUrl.placeholder = '默认可留空 (官方 OpenAI)';
    }
  } else if (provider === 'gemini') {
    els.modelName.value = els.modelName.value || 'gemini-1.5-pro';
    els.baseUrl.placeholder = 'Gemini 通常不需要 Base URL';
  } else if (provider === 'minimax') {
    if (!els.modelName.value || els.modelName.value === 'rule-fallback') {
      els.modelName.value = 'abab6.5-chat';
    }
    els.baseUrl.placeholder = '请填写 MiniMax OpenAI 兼容 Base URL';
  }
}

function isTargetRequired(actionName) {
  return actionName.startsWith('SKILL.') && actionName !== 'SKILL.PASS';
}

function isSpeechAction(actionName) {
  return actionName === 'SPEAK';
}

function cardTemplate(item, pending) {
  const legal = item.legal_actions || [];
  const card = document.createElement('div');
  card.className = 'card';

  const title = document.createElement('h3');
  title.textContent = `槽位 ${item.slot_id} (${item.is_human ? '你' : 'AI'})`;
  card.appendChild(title);

  const legalText = document.createElement('div');
  legalText.className = 'meta';
  legalText.textContent = `可行动作: ${legal.join(', ') || '无'}`;
  card.appendChild(legalText);

  if (!item.is_human || legal.length === 0) {
    return card;
  }

  const actionSelect = document.createElement('select');
  legal.forEach((a) => {
    const opt = document.createElement('option');
    opt.value = a;
    opt.textContent = a;
    actionSelect.appendChild(opt);
  });

  const targetInput = document.createElement('input');
  targetInput.type = 'number';
  targetInput.placeholder = 'target_id (如需要)';

  const speechInput = document.createElement('input');
  speechInput.placeholder = '发言内容 (SPEAK 时使用)';

  function updateActionForm() {
    const selected = actionSelect.value;
    const needTarget = isTargetRequired(selected);
    const needSpeech = isSpeechAction(selected);

    targetInput.style.display = needTarget ? 'block' : 'none';
    speechInput.style.display = needSpeech ? 'block' : 'none';

    if (selected === 'SKILL.GUARD') {
      targetInput.placeholder = '请输入当晚被刀目标';
    } else if (selected === 'SKILL.POISON') {
      targetInput.placeholder = '请输入毒药目标';
    } else if (selected === 'SKILL.KILL') {
      targetInput.placeholder = '请输入击杀目标';
    } else if (selected === 'SKILL.VERIFY') {
      targetInput.placeholder = '请输入查验目标';
    } else if (selected === 'SKILL.VOTE') {
      targetInput.placeholder = '请输入投票目标';
    }
  }

  actionSelect.addEventListener('change', updateActionForm);
  updateActionForm();

  const submitBtn = document.createElement('button');
  submitBtn.textContent = '提交动作';
  submitBtn.addEventListener('click', async () => {
    try {
      const selected = actionSelect.value;
      let payload;

      if (selected === 'SPEAK') {
        payload = {
          action: {
            action_type: 'SPEAK',
            data: {
              content: speechInput.value || `我是${item.slot_id}号，先给信息。`,
              is_whisper: false,
            },
          },
        };
      } else if (selected === 'SKILL.PASS') {
        payload = {
          action: {
            action_type: 'SKILL',
            data: {
              skill_name: 'VOTE',
              target_id: null,
            },
          },
        };
      } else {
        const skillName = selected.split('.')[1];
        const targetRaw = targetInput.value.trim();
        if (isTargetRequired(selected) && !targetRaw) {
          alert('该动作需要 target_id');
          return;
        }
        const targetId = targetRaw ? Number(targetRaw) : null;
        payload = {
          action: {
            action_type: 'SKILL',
            data: {
              skill_name: skillName,
              target_id: targetId,
            },
          },
        };
      }

      await api(`/games/${state.gameId}/actions/${item.slot_id}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      await refreshPending();
    } catch (err) {
      alert(`提交失败: ${err.message}`);
    }
  });

  card.appendChild(actionSelect);
  card.appendChild(targetInput);
  card.appendChild(speechInput);
  card.appendChild(submitBtn);
  return card;
}

async function refreshPending() {
  if (!state.gameId) return;
  try {
    const pending = await api(`/games/${state.gameId}/pending`);
    els.pendingMeta.textContent = `状态: ${pending.status} | 阶段: ${pending.stage} | 回合: ${pending.round}`;
    els.pendingList.innerHTML = '';
    pending.pending_actions.forEach((item) => {
      els.pendingList.appendChild(cardTemplate(item, pending));
    });

    if (pending.pending_actions.length === 0) {
      const d = document.createElement('div');
      d.className = 'warn';
      d.textContent = '当前无待行动作。你可以点 自动推进 AI 或 刷新历史。';
      els.pendingList.appendChild(d);
    }

    await refreshState();
  } catch (err) {
    alert(`刷新待行动失败: ${err.message}`);
  }
}

async function refreshHistory() {
  if (!state.gameId) return;
  try {
    const history = await api(`/games/${state.gameId}/history`);
    els.historyLog.textContent = pretty(history.history || []);
  } catch (err) {
    alert(`刷新历史失败: ${err.message}`);
  }
}

async function refreshState() {
  if (!state.gameId || !els.viewerSlot.value) return;
  try {
    const slot = Number(els.viewerSlot.value);
    const payload = await api(`/games/${state.gameId}/state/${slot}`);
    els.stateLog.textContent = pretty(payload);
  } catch (err) {
    alert(`刷新状态失败: ${err.message}`);
  }
}

async function createGame() {
  try {
    const provider = els.provider.value;
    const payload = {
      solo_human_mode: true,
      solo_human_slots: 5,
      model_provider: provider,
      model_name: els.modelName.value,
      temperature: Number(els.temperature.value),
      random_seed: Number(els.seed.value),
    };

    if (provider !== 'mock') {
      if (els.apiKey.value.trim()) {
        payload.model_api_key = els.apiKey.value.trim();
      }
      if (els.baseUrl.value.trim()) {
        payload.model_base_url = els.baseUrl.value.trim();
      }
    }

    const data = await api('/games/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    state.gameId = data.game_id;
    state.humanSlots = data.human_slots || [];
    renderViewerSlots();
    toggleControls(true);
    els.createResult.textContent = pretty(data);

    await refreshPending();
    await refreshHistory();
  } catch (err) {
    alert(`创建失败: ${err.message}`);
  }
}

async function autoplay() {
  if (!state.gameId) return;
  try {
    const data = await api(`/games/${state.gameId}/autoplay`, {
      method: 'POST',
      body: JSON.stringify({ max_actions: Number(els.maxActions.value) || 100 }),
    });
    els.createResult.textContent = `自动推进结果:\n${pretty(data)}`;
    await refreshPending();
    await refreshHistory();
  } catch (err) {
    alert(`自动推进失败: ${err.message}`);
  }
}

els.createGameBtn.addEventListener('click', createGame);
els.refreshBtn.addEventListener('click', refreshPending);
els.autoplayBtn.addEventListener('click', autoplay);
els.historyBtn.addEventListener('click', refreshHistory);
els.stateBtn.addEventListener('click', refreshState);
els.provider.addEventListener('change', updateProviderHints);

toggleControls(false);
updateProviderHints();
