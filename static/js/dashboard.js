(function () {
  function setError(message) {
    var box = document.getElementById("dash-error");
    if (!box) return;
    if (!message) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    box.classList.remove("hidden");
    box.textContent = message;
  }

  function renderCards(targetId, items) {
    var box = document.getElementById(targetId);
    box.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var div = document.createElement("div");
      div.className = "metric-card";
      div.innerHTML =
        "<div class=\"label\">" +
        item.label +
        "</div>" +
        "<div class=\"value\">" +
        item.value +
        "</div>";
      box.appendChild(div);
    }
  }

  function renderShortcuts(items) {
    var box = document.getElementById("shortcut-grid");
    box.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var a = document.createElement("a");
      a.className = "shortcut";
      a.href = item.url;
      a.textContent = item.label;
      box.appendChild(a);
    }
  }

  function refresh() {
    var bookId = document.getElementById("dash-book-id").value || "";
    var user = document.getElementById("dash-user").value || "";
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }

    var url =
      "/api/dashboard/workbench?book_id=" +
      encodeURIComponent(bookId) +
      (user ? "&user=" + encodeURIComponent(user) : "");

    fetch(url)
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
        var data = payload.data;
        renderCards("todo-cards", [
          { label: "待审核凭证", value: data.pending_vouchers },
          { label: "待审批报销", value: data.pending_reimbursements },
          { label: "待支付申请", value: data.pending_payments },
          { label: "未对账流水", value: data.unmatched_bank_transactions },
        ]);
        renderCards("alert-cards", [
          { label: "应收应付临期", value: data.arap_due_soon },
          { label: "应收应付逾期", value: data.arap_overdue },
        ]);
        renderShortcuts(data.shortcuts || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("dash-refresh").addEventListener("click", refresh);
    refresh();
  });
})();
