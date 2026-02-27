(function () {
  function setError(message, errors) {
    var box = document.getElementById("rule-error");
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

  function render(items) {
    var body = document.getElementById("rule-body");
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="4">暂无规则</td>';
      body.appendChild(empty);
      return;
    }
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.id +
        "</td><td>" +
        item.rule_key +
        "</td><td>" +
        (item.rule_value || "") +
        "</td><td>" +
        (item.description || "") +
        "</td>";
      body.appendChild(tr);
    }
  }

  function listRules() {
    fetchJson("/api/system/rules")
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

  function saveRule() {
    var payload = {
      rule_key: document.getElementById("rule-key").value,
      rule_value: document.getElementById("rule-value").value,
      description: document.getElementById("rule-desc").value,
    };

    fetchJson("/api/system/rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "保存失败", payload.data.errors);
          return;
        }
        setError("", []);
        listRules();
      })
      .catch(function () {
        setError("保存失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("rule-save").addEventListener("click", saveRule);
    listRules();
  });
})();
