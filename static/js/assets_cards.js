(function () {
  function toText(value) {
    if (value === null || value === undefined) return "";
    return String(value);
  }

  function setError(boxId, message, errors) {
    var box = document.getElementById(boxId);
    if (!box) return;
    if (!message && (!errors || errors.length === 0)) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    var lines = [];
    if (message) lines.push(message);
    if (errors && errors.length) {
      for (var i = 0; i < errors.length; i++) {
        var item = errors[i];
        var field = item.field ? item.field + "：" : "";
        lines.push(field + item.message);
      }
    }
    box.textContent = lines.join("\n");
    box.classList.remove("hidden");
  }

  function fetchJson(url, options) {
    return fetch(url, options).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    });
  }

  function initListPage() {
    var body = document.getElementById("asset-body");
    if (!body) return;

    function render(items) {
      body.innerHTML = "";
      if (!items || items.length === 0) {
        var empty = document.createElement("tr");
        empty.innerHTML = '<td colspan="7">暂无数据</td>';
        body.appendChild(empty);
        return;
      }
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var tr = document.createElement("tr");
        var statusClass = item.status === "ACTIVE" ? "status-pill active" : "status-pill";
        tr.innerHTML =
          "<td>" +
          toText(item.asset_code) +
          "</td>" +
          "<td>" +
          toText(item.asset_name) +
          "</td>" +
          "<td>" +
          toText(item.category_name) +
          "</td>" +
          "<td>" +
          toText(item.original_value) +
          "</td>" +
          "<td><span class=\"" +
          statusClass +
          "\">" +
          toText(item.status) +
          "</span></td>" +
          "<td>" +
          (item.is_enabled ? "启用" : "停用") +
          "</td>" +
          "<td>" +
          '<a class="btn small" href="/assets/' +
          item.id +
          '">编辑</a> ' +
          '<button class="btn small secondary" data-toggle-id="' +
          item.id +
          '" data-enabled="' +
          item.is_enabled +
          '">' +
          (item.is_enabled ? "停用" : "启用") +
          "</button>" +
          "</td>";
        body.appendChild(tr);
      }
    }

    function listAssets() {
      var bookId = document.getElementById("asset-book-id").value || "";
      if (!bookId) {
        setError("asset-error", "请填写账套ID");
        return;
      }
      fetchJson("/api/assets?book_id=" + encodeURIComponent(bookId))
        .then(function (payload) {
          if (!payload.ok) {
            setError("asset-error", payload.data.error || "查询失败", payload.data.errors);
            return;
          }
          setError("asset-error", "");
          render(payload.data.items || []);
        })
        .catch(function () {
          setError("asset-error", "查询失败");
        });
    }

    function toggleAsset(id, enabled) {
      fetchJson("/api/assets/" + id + "/enabled", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_enabled: enabled ? 0 : 1 }),
      })
        .then(function (payload) {
          if (!payload.ok) {
            setError("asset-error", payload.data.error || "更新失败", payload.data.errors);
            return;
          }
          setError("asset-error", "");
          listAssets();
        })
        .catch(function () {
          setError("asset-error", "更新失败");
        });
    }

    document.getElementById("asset-refresh").addEventListener("click", listAssets);
    document.addEventListener("click", function (e) {
      if (e.target && e.target.matches("button[data-toggle-id]")) {
        var id = e.target.getAttribute("data-toggle-id");
        var enabled = e.target.getAttribute("data-enabled") === "1";
        toggleAsset(id, enabled);
      }
    });

    listAssets();
  }

  function initDetailPage() {
    var saveBtn = document.getElementById("fa-save");
    if (!saveBtn) return;

    var assetId = document.getElementById("fa-id").value || "";
    var transferBtn = document.getElementById("fa-transfer");
    var disposeBtn = document.getElementById("fa-dispose");
    var scrapBtn = document.getElementById("fa-scrap");

    function getBookId() {
      return document.getElementById("fa-book-id").value || "";
    }

    function fillCategories(bookId, selectedId) {
      if (!bookId) {
        setError("fa-error", "请填写账套ID");
        return;
      }
      fetchJson("/api/assets/categories?book_id=" + encodeURIComponent(bookId))
        .then(function (payload) {
          if (!payload.ok) {
            setError("fa-error", payload.data.error || "加载类别失败", payload.data.errors);
            return;
          }
          var select = document.getElementById("fa-category");
          select.innerHTML = "";
          var items = payload.data.items || [];
          var hasOption = false;
          for (var i = 0; i < items.length; i++) {
            var item = items[i];
            if (item.is_enabled !== 1 && item.id !== selectedId) {
              continue;
            }
            var opt = document.createElement("option");
            opt.value = item.id;
            opt.textContent = item.code + " " + item.name + (item.is_enabled ? "" : "(停用)");
            if (selectedId && String(item.id) === String(selectedId)) {
              opt.selected = true;
            }
            select.appendChild(opt);
            hasOption = true;
          }
          if (!hasOption) {
            var optEmpty = document.createElement("option");
            optEmpty.value = "";
            optEmpty.textContent = "暂无可用类别";
            select.appendChild(optEmpty);
          }
          setError("fa-error", "");
        })
        .catch(function () {
          setError("fa-error", "加载类别失败");
        });
    }

    function fillForm(data) {
      document.getElementById("fa-book-id").value = data.book_id || "";
      document.getElementById("fa-code").value = data.asset_code || "";
      document.getElementById("fa-name").value = data.asset_name || "";
      document.getElementById("fa-status").value = data.status || "DRAFT";
      document.getElementById("fa-enabled").value = data.is_enabled ? "1" : "0";
      document.getElementById("fa-original").value = data.original_value || "";
      document.getElementById("fa-residual-rate").value = data.residual_rate || "";
      document.getElementById("fa-residual-value").value = data.residual_value || "";
      document.getElementById("fa-life").value = data.useful_life_months || "";
      document.getElementById("fa-method").value = data.depreciation_method || "STRAIGHT_LINE";
      document.getElementById("fa-start-date").value = data.start_use_date || "";
      document.getElementById("fa-cap-date").value = data.capitalization_date || "";
      document.getElementById("fa-dept").value = data.department_id || "";
      document.getElementById("fa-person").value = data.person_id || "";
      document.getElementById("fa-note").value = data.note || "";
      var codeInput = document.getElementById("fa-code");
      if (assetId) {
        codeInput.readOnly = true;
      }
    }

    function loadAsset() {
      if (!assetId) {
        fillCategories(getBookId(), null);
        return;
      }
      fetchJson("/api/assets/" + assetId)
        .then(function (payload) {
          if (!payload.ok) {
            setError("fa-error", payload.data.error || "加载失败", payload.data.errors);
            return;
          }
          fillForm(payload.data);
          fillCategories(payload.data.book_id, payload.data.category_id);
          setError("fa-error", "");
        })
        .catch(function () {
          setError("fa-error", "加载失败");
        });
    }

    function saveAsset() {
      var payload = {
        book_id: document.getElementById("fa-book-id").value,
        asset_code: document.getElementById("fa-code").value,
        asset_name: document.getElementById("fa-name").value,
        category_id: document.getElementById("fa-category").value,
        status: document.getElementById("fa-status").value,
        is_enabled: document.getElementById("fa-enabled").value,
        original_value: document.getElementById("fa-original").value,
        residual_rate: document.getElementById("fa-residual-rate").value,
        residual_value: document.getElementById("fa-residual-value").value,
        useful_life_months: document.getElementById("fa-life").value,
        depreciation_method: document.getElementById("fa-method").value,
        start_use_date: document.getElementById("fa-start-date").value,
        capitalization_date: document.getElementById("fa-cap-date").value,
        department_id: document.getElementById("fa-dept").value,
        person_id: document.getElementById("fa-person").value,
        note: document.getElementById("fa-note").value,
      };

      var url = assetId ? "/api/assets/" + assetId : "/api/assets";
      fetchJson(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (payload) {
          if (!payload.ok) {
            setError("fa-error", payload.data.error || "保存失败", payload.data.errors);
            return;
          }
          setError("fa-error", "");
          if (!assetId && payload.data && payload.data.id) {
            window.location.href = "/assets/" + payload.data.id;
            return;
          }
        })
        .catch(function () {
          setError("fa-error", "保存失败");
        });
    }

    function setChangeError(message, errors) {
      var box = document.getElementById("fa-change-error");
      if (!box) return;
      if (!message && (!errors || errors.length === 0)) {
        box.classList.add("hidden");
        box.textContent = "";
        return;
      }
      var lines = [];
      if (message) lines.push(message);
      if (errors && errors.length) {
        for (var i = 0; i < errors.length; i++) {
          var item = errors[i];
          var field = item.field ? item.field + "：" : "";
          lines.push(field + item.message);
        }
      }
      box.textContent = lines.join("\n");
      box.classList.remove("hidden");
    }

    function getChangePayload(type) {
      return {
        change_type: type,
        change_date: document.getElementById("fa-change-date").value,
        to_department_id: document.getElementById("fa-change-dept").value,
        to_person_id: document.getElementById("fa-change-person").value,
        note: document.getElementById("fa-change-note").value,
      };
    }

    function runChange(type, confirmText) {
      if (!assetId) {
        setChangeError("请先保存资产卡片");
        return;
      }
      if (!window.confirm(confirmText)) {
        return;
      }
      var payload = getChangePayload(type);
      fetchJson("/api/assets/" + assetId + "/change", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (payload) {
          if (!payload.ok) {
            setChangeError(payload.data.error || "操作失败", payload.data.errors);
            return;
          }
          setChangeError("操作成功", []);
          loadAsset();
        })
        .catch(function () {
          setChangeError("操作失败");
        });
    }

    document.getElementById("fa-book-id").addEventListener("change", function () {
      fillCategories(getBookId(), document.getElementById("fa-category").value);
    });
    saveBtn.addEventListener("click", saveAsset);
    if (transferBtn) {
      transferBtn.addEventListener("click", function () {
        runChange("TRANSFER", "确认执行资产转移？");
      });
    }
    if (disposeBtn) {
      disposeBtn.addEventListener("click", function () {
        runChange("DISPOSAL", "确认执行资产处置？");
      });
    }
    if (scrapBtn) {
      scrapBtn.addEventListener("click", function () {
        runChange("SCRAP", "确认执行资产报废？");
      });
    }

    loadAsset();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initListPage();
    initDetailPage();
  });
})();
