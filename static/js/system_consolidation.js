(function () {
  var VERSION = "CONSOLIDATION_REL_FIX2_V1";
  var state = {
    legalBooks: [],
    nonLegalBooks: [],
    virtualEntities: [],
    selectedVirtualId: "",
    naturalDraftByBookId: {},
    consolidationParams: null,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function currentRole() {
    var ctx = window.__MAIN_LAYOUT_CTX__ || {};
    var fromCtx = String(ctx.userRole || "").trim().toLowerCase();
    if (fromCtx) return fromCtx;
    try {
      return String(window.sessionStorage.getItem("xinyi_current_role") || window.localStorage.getItem("xinyi_current_role") || "")
        .trim()
        .toLowerCase();
    } catch (e) {
      return "";
    }
  }

  function isDebugVisible() {
    var r = currentRole();
    return r === "tester" || r === "admin";
  }

  function setMessage(type, text) {
    var e = $("conso-error");
    var o = $("conso-ok");
    if (!e || !o) return;
    e.classList.add("hidden");
    o.classList.add("hidden");
    e.textContent = "";
    o.textContent = "";
    if (!text) return;
    if (type === "error") {
      e.textContent = text;
      e.classList.remove("hidden");
    } else {
      o.textContent = text;
      o.classList.remove("hidden");
    }
  }

  function fetchJson(url, options) {
    return fetch(url, options || {})
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data || {} };
        });
      });
  }

  function fetchJsonWithStatus(url, options) {
    return fetch(url, options || {})
      .then(function (res) {
        return res.text().then(function (text) {
          var data = {};
          if (text) {
            try {
              data = JSON.parse(text);
            } catch (e) {
              data = {};
            }
          }
          return { ok: res.ok, status: res.status, data: data || {}, text: text || "" };
        });
      })
      .catch(function (err) {
        return { ok: false, status: 0, data: {}, text: String(err || "network_error") };
      });
  }

  function escapeHtml(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");
  }

  function normalizeBindError(message) {
    var msg = String(message || "").trim();
    if (!msg) return "保存关系失败";
    if (msg.indexOf("non_legal_book_id_required") >= 0 || msg.indexOf("legal_book_id_required") >= 0) {
      return "保存关系失败：缺少账套参数";
    }
    if (msg.indexOf("non_legal_book_id_invalid") >= 0 || msg.indexOf("legal_book_id_invalid") >= 0) {
      return "保存关系失败：账套ID格式不合法";
    }
    if (msg.indexOf("non_legal_and_legal_book_cannot_same") >= 0) {
      return "保存关系失败：非法人账套不能归属自身";
    }
    if (msg.indexOf("book_entity_kind_mismatch") >= 0) {
      return "保存关系失败：所选所属主体不是有效法人账套";
    }
    if (msg.indexOf("book_not_found") >= 0) {
      return "保存关系失败：账套不存在或已失效";
    }
    if (msg.indexOf("internal_error") >= 0) {
      return "保存关系失败：服务异常，请联系管理员并查看日志";
    }
    return msg;
  }

  function normalizeVirtualCreateError(message) {
    var msg = String(message || "").trim();
    if (!msg) return "新建虚拟主体失败：未知错误";
    if (msg.indexOf("virtual_code_required") >= 0) return "新建虚拟主体失败：编码必填";
    if (msg.indexOf("virtual_name_required") >= 0) return "新建虚拟主体失败：名称必填";
    if (msg.indexOf("virtual_code_duplicated") >= 0) return "新建虚拟主体失败：编码已存在";
    if (msg.indexOf("consolidation_model_not_ready") >= 0) return "新建虚拟主体失败：关系模型未就绪";
    if (msg.indexOf("internal_error") >= 0) return "新建虚拟主体失败：服务异常，请联系管理员并查看日志";
    return "新建虚拟主体失败：" + msg;
  }

  function normalizeMemberAddError(message) {
    var msg = String(message || "").trim();
    if (!msg) return "添加成员失败：未知错误";
    if (msg.indexOf("virtual_group_not_ready") >= 0) {
      return "添加成员失败：虚拟主体未完成分组初始化，请重试或联系管理员（virtual_group_not_ready）";
    }
    if (msg.indexOf("virtual_member_duplicated") >= 0) {
      return "添加成员失败：该法人账套已是当前虚拟主体成员（virtual_member_duplicated）";
    }
    if (msg.indexOf("legal_book_id_required") >= 0 || msg.indexOf("legal_book_id_invalid") >= 0) {
      return "添加成员失败：法人账套参数不合法（" + msg + "）";
    }
    if (msg.indexOf("internal_error") >= 0) {
      return "添加成员失败：服务异常，请联系管理员并查看日志（internal_error）";
    }
    return "添加成员失败：" + msg;
  }

  function bindTabs() {
    var buttons = document.querySelectorAll(".tab-btn");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function () {
        var tab = this.getAttribute("data-tab");
        var btns = document.querySelectorAll(".tab-btn");
        for (var j = 0; j < btns.length; j++) btns[j].classList.remove("active");
        this.classList.add("active");
        var panels = document.querySelectorAll(".tab-panel");
        for (var k = 0; k < panels.length; k++) panels[k].classList.remove("active");
        var panel = $("tab-" + tab);
        if (panel) panel.classList.add("active");
      });
    }
  }

  function getSelectedLegalInfo(selectEl) {
    if (!selectEl) return { value: "", text: "" };
    var value = String(selectEl.value || "").trim();
    var text = "";
    if (selectEl.selectedIndex >= 0) {
      var opt = selectEl.options[selectEl.selectedIndex];
      text = String((opt && opt.text) || "").trim();
    }
    return { value: value, text: text };
  }

  function updateNaturalRowDebug(row, source) {
    if (!row) return;
    var nonLegalBookId = String(row.getAttribute("data-non-legal-book-id") || "").trim();
    var selectEl = row.querySelector(".natural-legal-select");
    var debugEl = row.querySelector(".natural-debug");
    if (!debugEl) return;
    if (!isDebugVisible()) {
      debugEl.textContent = "";
      debugEl.style.display = "none";
      return;
    }
    debugEl.style.display = "";
    var selected = getSelectedLegalInfo(selectEl);
    var selectedText = selected.text || "未选择";
    var selectedValue = selected.value || "空";
    var from = source ? ("；来源=" + source) : "";
    debugEl.textContent =
      "调试 non_legal_book_id=" + nonLegalBookId +
      "；selected_label=" + selectedText +
      "；selected_submit_book_id=" + selectedValue +
      "；id口径=books.id" + from;
  }

  function syncVersionMarker() {
    var el = $("conso-version-marker");
    if (!el) return;
    el.textContent = VERSION;
  }

  function renderNaturalTable() {
    var body = $("natural-body");
    if (!body) return;
    body.innerHTML = "";
    if (!state.nonLegalBooks.length) {
      body.innerHTML = '<tr><td colspan="4">暂无非法人账套数据</td></tr>';
      return;
    }
    var options = '<option value="">请选择法人账套</option>';
    for (var i = 0; i < state.legalBooks.length; i++) {
      var l = state.legalBooks[i];
      options += '<option value="' + escapeHtml(l.book_id) + '">' + escapeHtml(l.book_name || "") + "（" + escapeHtml(l.book_code || "") + "）</option>";
    }
    for (var j = 0; j < state.nonLegalBooks.length; j++) {
      var n = state.nonLegalBooks[j];
      var tr = document.createElement("tr");
      tr.setAttribute("data-non-legal-book-id", String(n.book_id || ""));
      tr.innerHTML =
        "<td>" + escapeHtml(n.book_name || "") + "（" + escapeHtml(n.book_code || "") + "）</td>" +
        "<td>" + (n.parent_legal_book_name ? escapeHtml(n.parent_legal_book_name) + "（ID:" + escapeHtml(n.parent_legal_book_id) + "）" : "<未绑定>") + "</td>" +
        "<td><select class=\"field-input natural-legal-select\" data-book-id=\"" + escapeHtml(n.book_id) + "\">" + options + "</select><div class=\"natural-debug\"></div></td>" +
        "<td><button class=\"btn secondary bind-btn\" type=\"button\" data-book-id=\"" + n.book_id + "\">保存关系</button></td>";
      body.appendChild(tr);
      var sel = tr.querySelector(".natural-legal-select");
      if (sel) {
        var draft = String(state.naturalDraftByBookId[String(n.book_id || "")] || "").trim();
        if (draft) {
          sel.value = draft;
        } else if (n.parent_legal_book_id) {
          sel.value = String(n.parent_legal_book_id);
        }
      }
      updateNaturalRowDebug(tr, "render");
    }
  }

  function renderVirtualTable() {
    var body = $("virtual-body");
    if (!body) return;
    body.innerHTML = "";
    if (!state.virtualEntities.length) {
      body.innerHTML = '<tr><td colspan="6">暂无虚拟主体</td></tr>';
      return;
    }
    for (var i = 0; i < state.virtualEntities.length; i++) {
      var v = state.virtualEntities[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + v.id + "</td>" +
        "<td>" + (v.virtual_code || "") + "</td>" +
        "<td>" + (v.virtual_name || "") + "</td>" +
        "<td>" + (v.status || "") + "/" + (v.is_enabled ? "启用" : "停用") + "</td>" +
        "<td>" + (v.member_count || 0) + "</td>" +
        "<td><button class=\"btn secondary choose-virtual-btn\" type=\"button\" data-virtual-id=\"" + v.id + "\">管理成员</button></td>";
      body.appendChild(tr);
    }
  }

  function renderMemberSelectors() {
    var virtualSel = $("member-virtual-id");
    var legalSel = $("member-legal-book-id");
    if (!virtualSel || !legalSel) return;
    virtualSel.innerHTML = '<option value="">请选择虚拟主体</option>';
    for (var i = 0; i < state.virtualEntities.length; i++) {
      var v = state.virtualEntities[i];
      var opt = document.createElement("option");
      opt.value = String(v.id);
      opt.textContent = (v.virtual_name || "") + "（" + (v.virtual_code || "") + "）";
      virtualSel.appendChild(opt);
    }
    legalSel.innerHTML = '<option value="">请选择法人账套</option>';
    for (var j = 0; j < state.legalBooks.length; j++) {
      var l = state.legalBooks[j];
      var op = document.createElement("option");
      op.value = String(l.book_id);
      op.textContent = (l.book_name || "") + "（" + (l.book_code || "") + "）";
      legalSel.appendChild(op);
    }
    if (state.selectedVirtualId) virtualSel.value = state.selectedVirtualId;
  }

  function loadOverview() {
    setMessage("", "");
    return fetchJson("/api/consolidation/relations/overview")
      .then(function (ret) {
        if (!ret.ok) {
          setMessage("error", ret.data.error || "加载关系数据失败");
          return;
        }
        state.legalBooks = ret.data.legal_books || [];
        state.nonLegalBooks = ret.data.non_legal_books || [];
        state.virtualEntities = ret.data.virtual_entities || [];
        renderNaturalTable();
        renderVirtualTable();
        renderMemberSelectors();
      })
      .catch(function () {
        setMessage("error", "加载关系数据失败");
      });
  }

  function bindNaturalActions() {
    var body = $("natural-body");
    if (!body) return;
    body.addEventListener("change", function (e) {
      var target = e.target;
      if (!target || !target.classList || !target.classList.contains("natural-legal-select")) return;
      var row = target.closest("tr");
      if (row) {
        var rid = String(row.getAttribute("data-non-legal-book-id") || "").trim();
        if (rid) state.naturalDraftByBookId[rid] = String(target.value || "").trim();
      }
      updateNaturalRowDebug(row, "change");
    });
    body.addEventListener("input", function (e) {
      var target = e.target;
      if (!target || !target.classList || !target.classList.contains("natural-legal-select")) return;
      var row = target.closest("tr");
      updateNaturalRowDebug(row, "input");
    });
    body.addEventListener("click", function (e) {
      var target = e.target;
      if (!target || !target.classList || !target.classList.contains("natural-legal-select")) return;
      var row = target.closest("tr");
      window.setTimeout(function () {
        updateNaturalRowDebug(row, "click");
      }, 0);
    });
    body.addEventListener("click", function (e) {
      var btn = e.target;
      if (!btn || !btn.classList.contains("bind-btn")) return;
      var nonLegalBookId = String(btn.getAttribute("data-book-id") || "");
      var row = btn.closest("tr");
      var sel = row ? row.querySelector(".natural-legal-select") : null;
      var selected = getSelectedLegalInfo(sel);
      var legalBookId = String(selected.value || "");
      updateNaturalRowDebug(row, "save_click");
      if (!nonLegalBookId || !legalBookId) {
        setMessage("error", "请选择所属法人账套后再保存");
        return;
      }
      fetchJson("/api/consolidation/relations/non-legal-bind", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ non_legal_book_id: nonLegalBookId, legal_book_id: legalBookId }),
      }).then(function (ret) {
        if (!ret.ok) {
          setMessage("error", normalizeBindError(ret.data.error || "保存关系失败"));
          return;
        }
        state.naturalDraftByBookId[nonLegalBookId] = legalBookId;
        setMessage("ok", "非法人归属法人关系已更新");
        loadOverview();
      }).catch(function () {
        setMessage("error", "保存关系失败：网络异常或服务未响应");
      });
    });
  }

  function bindVirtualActions() {
    var createBtn = $("create-virtual-btn");
    if (createBtn) {
      createBtn.addEventListener("click", function () {
        var code = String(($("virtual-code").value || "")).trim();
        var name = String(($("virtual-name").value || "")).trim();
        var note = String(($("virtual-note").value || "")).trim();
        if (!code || !name) {
          setMessage("error", "虚拟主体编码和名称必填");
          return;
        }
        fetchJson("/api/consolidation/virtual-entities", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ virtual_code: code, virtual_name: name, note: note }),
        }).then(function (ret) {
          if (!ret.ok) {
            setMessage("error", normalizeVirtualCreateError(ret.data.error || "internal_error"));
            return;
          }
          setMessage("ok", "虚拟主体创建成功");
          $("virtual-code").value = "";
          $("virtual-name").value = "";
          $("virtual-note").value = "";
          state.selectedVirtualId = String(ret.data.id || "");
          loadOverview().then(function () {
            loadMembers(state.selectedVirtualId);
          });
        }).catch(function () {
          setMessage("error", "新建虚拟主体失败：网络异常或服务未响应");
        });
      });
    }

    var vbody = $("virtual-body");
    if (vbody) {
      vbody.addEventListener("click", function (e) {
        var btn = e.target;
        if (!btn || !btn.classList.contains("choose-virtual-btn")) return;
        var id = String(btn.getAttribute("data-virtual-id") || "");
        if (!id) return;
        state.selectedVirtualId = id;
        var tabBtn = document.querySelector('.tab-btn[data-tab="members"]');
        if (tabBtn) tabBtn.click();
        renderMemberSelectors();
        loadMembers(id);
      });
    }
  }

  function loadMembers(virtualId) {
    var id = String(virtualId || "");
    if (!id) {
      $("member-body").innerHTML = '<tr><td colspan="6">请选择虚拟主体后查看</td></tr>';
      $("member-virtual-name").textContent = "-";
      return;
    }
    fetchJson("/api/consolidation/virtual-entities/" + encodeURIComponent(id) + "/members")
      .then(function (ret) {
        if (!ret.ok) {
          setMessage("error", ret.data.error || "加载成员失败");
          return;
        }
        var data = ret.data || {};
        var entity = data.virtual_entity || {};
        $("member-virtual-name").textContent = (entity.virtual_name || "") + "（" + (entity.virtual_code || "") + "）";
        var items = data.items || [];
        var body = $("member-body");
        body.innerHTML = "";
        if (!items.length) {
          body.innerHTML = '<tr><td colspan="6">暂无法人成员</td></tr>';
          return;
        }
        for (var i = 0; i < items.length; i++) {
          var m = items[i];
          var tr = document.createElement("tr");
          tr.innerHTML =
            "<td>" + m.id + "</td>" +
            "<td>" + (m.book_name || "") + "</td>" +
            "<td>" + (m.book_code || "") + "</td>" +
            "<td>" + (m.status || "") + "</td>" +
            "<td>" + (m.is_enabled ? "是" : "否") + "</td>" +
            "<td>" + (m.is_enabled ? '<button class="btn secondary disable-member-btn" data-member-id="' + m.id + '" type="button">停用</button>' : '-') + "</td>";
          body.appendChild(tr);
        }
      })
      .catch(function () {
        setMessage("error", "加载成员失败");
      });
  }

  function bindMemberActions() {
    var addBtn = $("add-member-btn");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        var virtualId = String(($("member-virtual-id").value || "")).trim();
        var legalBookId = String(($("member-legal-book-id").value || "")).trim();
        if (!virtualId || !legalBookId) {
          setMessage("error", "请选择虚拟主体和法人账套");
          return;
        }
        fetchJson("/api/consolidation/virtual-entities/" + encodeURIComponent(virtualId) + "/members", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ legal_book_id: legalBookId }),
        }).then(function (ret) {
          if (!ret.ok) {
            setMessage("error", normalizeMemberAddError(ret.data.error || "internal_error"));
            return;
          }
          setMessage("ok", "法人成员添加成功");
          state.selectedVirtualId = virtualId;
          loadOverview().then(function () {
            loadMembers(virtualId);
          });
        }).catch(function () {
          setMessage("error", "添加成员失败：网络异常或服务未响应");
        });
      });
    }

    var refreshBtn = $("refresh-member-btn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        var virtualId = String(($("member-virtual-id").value || state.selectedVirtualId || "")).trim();
        if (!virtualId) {
          setMessage("error", "请先选择虚拟主体");
          return;
        }
        loadMembers(virtualId);
      });
    }

    var virtualSel = $("member-virtual-id");
    if (virtualSel) {
      virtualSel.addEventListener("change", function () {
        var id = String(virtualSel.value || "");
        state.selectedVirtualId = id;
        loadMembers(id);
      });
    }

    var body = $("member-body");
    if (body) {
      body.addEventListener("click", function (e) {
        var btn = e.target;
        if (!btn || !btn.classList.contains("disable-member-btn")) return;
        var memberId = String(btn.getAttribute("data-member-id") || "");
        if (!memberId) return;
        fetchJson("/api/consolidation/members/" + encodeURIComponent(memberId) + "/disable", {
          method: "POST",
        }).then(function (ret) {
          if (!ret.ok) {
            setMessage("error", ret.data.error || "停用成员失败");
            return;
          }
          setMessage("ok", "成员已停用");
          loadMembers(state.selectedVirtualId);
          loadOverview();
        }).catch(function () {
          setMessage("error", "停用成员失败");
        });
      });
    }
  }

  function setParamFeedback(text, isError) {
    var el = $("conso-param-feedback");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = isError ? "#b42318" : "#344054";
  }

  function renderConsolidationParams(payload) {
    state.consolidationParams = payload || {};
    var items = (state.consolidationParams && state.consolidationParams.items) || [];
    var jsonBox = $("conso-param-json");
    var hint = $("conso-param-empty-hint");
    if (hint) {
      hint.style.display = items.length ? "none" : "";
    }
    if (jsonBox) {
      jsonBox.textContent = JSON.stringify(state.consolidationParams || {}, null, 2);
    }
    if (!items.length) return;
    var latest = items[0] || {};
    if ($("conso-param-group-id") && !String($("conso-param-group-id").value || "").trim()) {
      $("conso-param-group-id").value = String(latest.consolidation_group_id || "");
    }
    if ($("conso-param-start-period")) {
      $("conso-param-start-period").value = String(latest.start_period || "");
    }
    if ($("conso-param-note")) {
      $("conso-param-note").value = String(latest.note || "");
    }
  }

  function loadConsolidationParams() {
    var gid = String(($("conso-param-group-id") && $("conso-param-group-id").value) || "").trim();
    var url = "/api/consolidation/parameters";
    if (gid) url += "?consolidation_group_id=" + encodeURIComponent(gid);
    return fetchJsonWithStatus(url).then(function (ret) {
      if (!ret.ok) {
        var errText = (ret.data && (ret.data.error || ret.data.message)) || ret.text || "unknown_error";
        setParamFeedback("参数加载失败 status=" + ret.status + " detail=" + errText, true);
        return;
      }
      renderConsolidationParams(ret.data || {});
      setParamFeedback("参数已加载 status=" + ret.status, false);
    });
  }

  function bindConsolidationParams() {
    var reloadBtn = $("conso-param-reload-btn");
    if (reloadBtn) {
      reloadBtn.addEventListener("click", function () {
        loadConsolidationParams();
      });
    }

    var saveBtn = $("conso-param-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        var gid = String(($("conso-param-group-id") && $("conso-param-group-id").value) || "").trim();
        var startPeriod = String(($("conso-param-start-period") && $("conso-param-start-period").value) || "").trim();
        var note = String(($("conso-param-note") && $("conso-param-note").value) || "").trim();
        if (!gid) {
          setParamFeedback("参数保存失败：缺少 consolidation_group_id", true);
          return;
        }
        if (!startPeriod) {
          setParamFeedback("参数保存失败：缺少 start_period", true);
          return;
        }
        fetchJsonWithStatus("/api/consolidation/parameters", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            consolidation_group_id: Number(gid),
            start_period: startPeriod,
            note: note,
          }),
        }).then(function (ret) {
          if (!ret.ok) {
            var errText = (ret.data && (ret.data.error || ret.data.message)) || ret.text || "unknown_error";
            setParamFeedback("参数保存失败 status=" + ret.status + " detail=" + errText, true);
            return;
          }
          setParamFeedback("参数保存成功 status=" + ret.status, false);
          loadConsolidationParams();
        });
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    syncVersionMarker();
    bindTabs();
    bindNaturalActions();
    bindVirtualActions();
    bindMemberActions();
    bindConsolidationParams();
    loadOverview();
    loadConsolidationParams();
  });
})();
