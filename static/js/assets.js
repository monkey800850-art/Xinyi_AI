(function () {
  function setError(message) {
    var box = document.getElementById("asset-error");
    if (!box) return;
    if (!message) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    box.classList.remove("hidden");
    box.textContent = message;
  }

  function renderList(items) {
    var body = document.getElementById("asset-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.id +
        "</td>" +
        "<td>" +
        item.code +
        "</td>" +
        "<td>" +
        item.name +
        "</td>" +
        "<td>" +
        item.depreciation_method +
        "</td>" +
        "<td>" +
        item.default_useful_life_months +
        "</td>" +
        "<td>" +
        item.default_residual_rate +
        "</td>" +
        "<td>" +
        (item.expense_subject_code || "") +
        "</td>" +
        "<td>" +
        (item.accumulated_depr_subject_code || "") +
        "</td>" +
        "<td>" +
        item.is_enabled +
        "</td>" +
        '<td><button class="btn small" data-id="' +
        item.id +
        '" data-enabled="' +
        item.is_enabled +
        '">' +
        (item.is_enabled ? "停用" : "启用") +
        "</button></td>";
      body.appendChild(tr);
    }
  }

  function listCategories() {
    var bookId = document.getElementById("asset-book-id").value || "";
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }
    fetch("/api/assets/categories?book_id=" + encodeURIComponent(bookId))
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "查询失败");
          return;
        }
        setError("");
        renderList(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function addCategory() {
    var payload = {
      book_id: document.getElementById("asset-book-id").value,
      code: document.getElementById("asset-code").value,
      name: document.getElementById("asset-name").value,
      depreciation_method: document.getElementById("asset-method").value,
      default_useful_life_months: document.getElementById("asset-life").value,
      default_residual_rate: document.getElementById("asset-residual").value,
      expense_subject_code: document.getElementById("asset-expense").value,
      accumulated_depr_subject_code: document.getElementById("asset-accum").value,
    };

    fetch("/api/assets/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "新增失败");
          return;
        }
        setError("");
        listCategories();
      })
      .catch(function () {
        setError("新增失败");
      });
  }

  function toggleCategory(id, enabled) {
    fetch("/api/assets/categories/" + id + "/enabled", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_enabled: enabled ? 0 : 1 }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "更新失败");
          return;
        }
        setError("");
        listCategories();
      })
      .catch(function () {
        setError("更新失败");
      });
  }

  document.addEventListener("click", function (e) {
    if (e.target && e.target.matches("button[data-id]")) {
      var id = e.target.getAttribute("data-id");
      var enabled = e.target.getAttribute("data-enabled") === "1";
      toggleCategory(id, enabled);
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("asset-add").addEventListener("click", addCategory);
    listCategories();
  });
})();
