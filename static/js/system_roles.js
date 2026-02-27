(function () {
  function setError(message, errors) {
    var box = document.getElementById("role-error");
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
    var body = document.getElementById("role-body");
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="6">暂无角色</td>';
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
        item.code +
        "</td><td>" +
        item.name +
        "</td><td>" +
        item.data_scope +
        "</td><td>" +
        (item.permissions || []).join(",") +
        "</td><td>" +
        (item.is_enabled ? "启用" : "停用") +
        "</td>";
      body.appendChild(tr);
    }
  }

  function listRoles() {
    fetchJson("/api/system/roles")
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

  function saveRole() {
    var payload = {
      code: document.getElementById("role-code").value,
      name: document.getElementById("role-name").value,
      description: document.getElementById("role-desc").value,
      data_scope: document.getElementById("role-scope").value,
      is_enabled: document.getElementById("role-enabled").value,
    };

    var permText = document.getElementById("role-perms").value || "";
    var perms = permText
      .split(",")
      .map(function (val) {
        return val.trim();
      })
      .filter(function (val) {
        return val;
      });

    fetchJson("/api/system/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "保存失败", payload.data.errors);
          return;
        }
        var id = payload.data.id;
        if (perms.length) {
          return fetchJson("/api/system/roles/" + id + "/permissions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ permissions: perms }),
          });
        }
        return { ok: true };
      })
      .then(function (payload) {
        if (payload && payload.ok === false) {
          setError(payload.data.error || "保存失败", payload.data.errors);
          return;
        }
        setError("", []);
        listRoles();
      })
      .catch(function () {
        setError("保存失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("role-save").addEventListener("click", saveRole);
    listRoles();
  });
})();
