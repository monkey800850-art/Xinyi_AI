(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(id, message) {
    var box = document.getElementById(id);
    if (!box) {
      return;
    }
    if (!message) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    box.classList.remove("hidden");
    box.textContent = message;
  }

  function qs(id) {
    return document.getElementById(id);
  }

  function downloadExport(url) {
    fetch(url)
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (data) {
            throw new Error(data.error || "导出失败");
          });
        }
        return res.blob();
      })
      .then(function (blob) {
        var link = document.createElement("a");
        link.href = window.URL.createObjectURL(blob);
        link.download = "payments.xlsx";
        link.click();
        window.URL.revokeObjectURL(link.href);
      })
      .catch(function (err) {
        setError("pay-error", err.message || "导出失败");
      });
  }

  function renderList(items) {
    var body = qs("pay-body");
    if (!body) return;
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.id +
        "</td>" +
        "<td>" +
        item.title +
        "</td>" +
        "<td>" +
        item.payee_name +
        "</td>" +
        "<td>" +
        item.pay_method +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.amount) +
        "</td>" +
        "<td>" +
        item.status +
        "</td>" +
        "<td>" +
        (item.reimbursement_id || "-") +
        "</td>" +
        '<td><a class="btn small" href="/payments/' +
        item.id +
        '">查看</a></td>';
      body.appendChild(tr);
    }
  }

  function listPayments() {
    var bookId = qs("pay-book-id").value || "";
    var status = qs("pay-status").value || "";
    if (!bookId) {
      setError("pay-error", "请填写账套ID");
      return;
    }

    var url =
      "/api/payments?book_id=" +
      encodeURIComponent(bookId) +
      (status ? "&status=" + encodeURIComponent(status) : "");

    fetch(url)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("pay-error", payload.data.error || "查询失败");
          return;
        }
        setError("pay-error", "");
        renderList(payload.data.items || []);
      })
      .catch(function () {
        setError("pay-error", "查询失败");
      });
  }

  function exportPayments() {
    var bookId = qs("pay-book-id").value || "";
    var status = qs("pay-status").value || "";
    if (!bookId) {
      setError("pay-error", "请填写账套ID");
      return;
    }

    var url =
      "/api/exports/payments?book_id=" +
      encodeURIComponent(bookId) +
      (status ? "&status=" + encodeURIComponent(status) : "");
    downloadExport(url);
  }

  function renderLogs(logs) {
    var body = qs("pay-logs-body");
    if (!body) return;
    body.innerHTML = "";
    for (var i = 0; i < logs.length; i++) {
      var l = logs[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        l.action +
        "</td>" +
        "<td>" +
        l.from_status +
        " → " +
        l.to_status +
        "</td>" +
        "<td>" +
        l.operator +
        "</td>" +
        "<td>" +
        l.operator_role +
        "</td>" +
        "<td>" +
        (l.comment || "") +
        "</td>" +
        "<td>" +
        l.created_at +
        "</td>";
      body.appendChild(tr);
    }
  }

  function loadDetail() {
    var id = qs("payment-id");
    if (!id) return;
    var pid = id.value;
    if (!pid) return;

    fetch("/api/payments/" + pid)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("payment-error", payload.data.error || "加载失败");
          return;
        }
        var data = payload.data;
        qs("payment-title").value = data.title;
        qs("payment-payee").value = data.payee_name;
        qs("payment-account").value = data.payee_account;
        qs("payment-method").value = data.pay_method;
        qs("payment-amount").value = data.amount;
        qs("payment-reimbursement-id").value = data.reimbursement_id || "";
        qs("payment-status").textContent = data.status;
        qs("payment-reject-reason").textContent = data.reject_reason || "-";
        renderLogs(data.logs || []);
      })
      .catch(function () {
        setError("payment-error", "加载失败");
      });
  }

  function saveDetail() {
    var payload = {
      id: qs("payment-id")?.value || "",
      book_id: qs("payment-book-id").value,
      title: qs("payment-title").value,
      payee_name: qs("payment-payee").value,
      payee_account: qs("payment-account").value,
      pay_method: qs("payment-method").value,
      amount: qs("payment-amount").value,
      reimbursement_id: qs("payment-reimbursement-id").value,
      status: "draft",
    };

    fetch("/api/payments", {
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
          setError("payment-error", payload.data.error || "保存失败");
          return;
        }
        setError("payment-error", "");
        window.location.href = "/payments/" + payload.data.id;
      })
      .catch(function () {
        setError("payment-error", "保存失败");
      });
  }

  function submitDetail() {
    var id = qs("payment-id").value;
    var operator = qs("payment-operator").value || "";
    var role = qs("payment-role").value || "";

    fetch("/api/payments/" + id + "/submit", {
      method: "POST",
      headers: {
        "X-User": operator,
        "X-Role": role,
      },
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("payment-error", payload.data.error || "提交失败");
          return;
        }
        setError("payment-error", "");
        window.location.reload();
      })
      .catch(function () {
        setError("payment-error", "提交失败");
      });
  }

  function approveDetail(approve, reason) {
    var id = qs("payment-id").value;
    var operator = qs("payment-operator").value || "";
    var role = qs("payment-role").value || "";
    var url = "/api/payments/" + id + (approve ? "/approve" : "/reject");

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User": operator,
        "X-Role": role,
      },
      body: approve ? JSON.stringify({ comment: reason || "" }) : JSON.stringify({ reason: reason || "" }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("payment-error", payload.data.error || "审批失败");
          return;
        }
        setError("payment-error", "");
        window.location.reload();
      })
      .catch(function () {
        setError("payment-error", "审批失败");
      });
  }

  function executeDetail() {
    var id = qs("payment-id").value;
    var operator = qs("payment-operator").value || "";
    var role = qs("payment-role").value || "";

    fetch("/api/payments/" + id + "/execute", {
      method: "POST",
      headers: {
        "X-User": operator,
        "X-Role": role,
      },
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("payment-error", payload.data.error || "执行失败");
          return;
        }
        setError("payment-error", "");
        window.location.reload();
      })
      .catch(function () {
        setError("payment-error", "执行失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (qs("pay-query")) {
      qs("pay-query").addEventListener("click", listPayments);
      if (qs("pay-export")) {
        qs("pay-export").addEventListener("click", exportPayments);
      }
      listPayments();
    }

    if (qs("payment-save")) {
      qs("payment-save").addEventListener("click", saveDetail);
      qs("payment-submit").addEventListener("click", submitDetail);
      qs("payment-approve").addEventListener("click", function () {
        approveDetail(true, prompt("审批意见（可空）") || "");
      });
      qs("payment-reject").addEventListener("click", function () {
        var reason = prompt("驳回原因（必填）") || "";
        approveDetail(false, reason);
      });
      qs("payment-execute").addEventListener("click", executeDetail);
      loadDetail();
    }
  });
})();
