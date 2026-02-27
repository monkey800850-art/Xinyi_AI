(function () {
  function setError(message, errors) {
    var box = document.getElementById("user-error");
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
    var body = document.getElementById("user-body");
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="6">暂无用户</td>';
      body.appendChild(empty);
      return;
    }
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var roles = (item.roles || []).map(function (r) {
        return r.code || r.name || r.id;
      });
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.id +
        "</td><td>" +
        item.username +
        "</td><td>" +
        (item.display_name || "") +
        "</td><td>" +
        roles.join(",") +
        "</td><td>" +
        (item.is_enabled ? "启用" : "停用") +
        "</td><td>" +
        '<button class="btn small" data-id="' +
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

  function listUsers() {
    fetchJson("/api/system/users")
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

  function saveUser() {
    var payload = {
      username: document.getElementById("user-username").value,
      display_name: document.getElementById("user-display").value,
      is_enabled: document.getElementById("user-enabled").value,
    };

    var roleText = document.getElementById("user-roles").value || "";
    var roleIds = roleText
      .split(",")
      .map(function (val) {
        return parseInt(val, 10);
      })
      .filter(function (val) {
        return !isNaN(val);
      });

    fetchJson("/api/system/users", {
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
        if (roleIds.length) {
          return fetchJson("/api/system/users/" + id + "/roles", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role_ids: roleIds }),
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
        listUsers();
      })
      .catch(function () {
        setError("保存失败");
      });
  }

  function toggleUser(id, enabled) {
    fetchJson("/api/system/users/" + id + "/enabled", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_enabled: enabled ? 0 : 1 }),
    })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "更新失败", payload.data.errors);
          return;
        }
        setError("", []);
        listUsers();
      })
      .catch(function () {
        setError("更新失败");
      });
  }

  document.addEventListener("click", function (e) {
    if (e.target && e.target.matches("button[data-id]")) {
      var id = e.target.getAttribute("data-id");
      var enabled = e.target.getAttribute("data-enabled") === "1";
      toggleUser(id, enabled);
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("user-save").addEventListener("click", saveUser);
    listUsers();
  });
})();
