(function () {
  function setError(message, errors) {
    var box = document.getElementById("audit-error");
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

  function fetchJson(url) {
    return fetch(url).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    });
  }

  function render(items) {
    var body = document.getElementById("audit-body");
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="8">暂无日志</td>';
      body.appendChild(empty);
      return;
    }
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.created_at +
        "</td><td>" +
        item.module +
        "</td><td>" +
        item.action +
        "</td><td>" +
        (item.entity_type || "") +
        "</td><td>" +
        (item.entity_id || "") +
        "</td><td>" +
        (item.operator || "") +
        "</td><td>" +
        (item.operator_role || "") +
        "</td><td>" +
        JSON.stringify(item.detail || {}) +
        "</td>";
      body.appendChild(tr);
    }
  }

  function query() {
    var module = document.getElementById("audit-module").value || "";
    var action = document.getElementById("audit-action").value || "";
    var operator = document.getElementById("audit-operator").value || "";
    var start = document.getElementById("audit-start").value || "";
    var end = document.getElementById("audit-end").value || "";

    var url =
      "/api/system/audit?module=" +
      encodeURIComponent(module) +
      "&action=" +
      encodeURIComponent(action) +
      "&operator=" +
      encodeURIComponent(operator) +
      "&start_date=" +
      encodeURIComponent(start) +
      "&end_date=" +
      encodeURIComponent(end);

    fetchJson(url)
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "查询失败", payload.data.errors);
          return;
        }
        setError("", []);
        render(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("audit-query").addEventListener("click", query);
    query();
  });
})();
