(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(message) {
    var box = document.getElementById("rec-error");
    if (!box) return;
    if (!message) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    box.classList.remove("hidden");
    box.textContent = message;
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
        link.download = "bank_reconcile.xlsx";
        link.click();
        window.URL.revokeObjectURL(link.href);
      })
      .catch(function (err) {
        setError(err.message || "导出失败");
      });
  }
  function renderSummary(data) {
    var box = document.getElementById("rec-summary");
    box.textContent =
      "总笔数：" +
      data.total +
      "，未匹配：" +
      data.unmatched_count +
      "（金额：" +
      formatAmount(data.unmatched_amount) +
      "），已匹配金额：" +
      formatAmount(data.matched_amount) +
      "，最新余额：" +
      (data.latest_balance === null ? "-" : formatAmount(data.latest_balance));
  }

  function renderList(items) {
    var body = document.getElementById("rec-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.id +
        "</td>" +
        "<td>" +
        item.txn_date +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.amount) +
        "</td>" +
        "<td>" +
        (item.summary || "") +
        "</td>" +
        "<td>" +
        item.match_status +
        "</td>" +
        "<td>" +
        (item.matched_voucher_id || "-") +
        "</td>" +
        '<td><button class="btn small" data-id="' +
        item.id +
        '" data-voucher="' +
        (item.matched_voucher_id || "") +
        '">填充</button></td>';
      body.appendChild(tr);
    }

    body.addEventListener("click", function (e) {
      var target = e.target;
      if (target && target.matches("button[data-id]")) {
        document.getElementById("manual-txn-id").value = target.getAttribute(
          "data-id"
        );
        document.getElementById("manual-voucher-id").value = target.getAttribute(
          "data-voucher"
        );
      }
    });
  }

  function getParams() {
    return {
      book_id: document.getElementById("rec-book-id").value || "",
      bank_account_id:
        document.getElementById("rec-bank-account-id").value || "",
      date_tolerance: document.getElementById("rec-tolerance").value || "3",
    };
  }

  function refresh() {
    var params = getParams();
    if (!params.book_id) {
      setError("请填写账套ID");
      return;
    }

    var url =
      "/api/reconcile/list?book_id=" +
      encodeURIComponent(params.book_id) +
      (params.bank_account_id
        ? "&bank_account_id=" + encodeURIComponent(params.bank_account_id)
        : "");
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
        renderList(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });

    var reportUrl =
      "/api/reconcile/report?book_id=" +
      encodeURIComponent(params.book_id) +
      (params.bank_account_id
        ? "&bank_account_id=" + encodeURIComponent(params.bank_account_id)
        : "");
    fetch(reportUrl)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (payload.ok) {
          renderSummary(payload.data);
        }
      });
  }

  function autoMatch() {
    var params = getParams();
    if (!params.book_id) {
      setError("请填写账套ID");
      return;
    }

    var url =
      "/api/reconcile/auto?book_id=" +
      encodeURIComponent(params.book_id) +
      (params.bank_account_id
        ? "&bank_account_id=" + encodeURIComponent(params.bank_account_id)
        : "") +
      "&date_tolerance=" +
      encodeURIComponent(params.date_tolerance);

    fetch(url, { method: "POST" })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "匹配失败");
          return;
        }
        setError("");
        refresh();
      })
      .catch(function () {
        setError("匹配失败");
      });
  }

  function exportReport() {
    var params = getParams();
    if (!params.book_id) {
      setError("请填写账套ID");
      return;
    }

    var url =
      "/api/exports/bank_reconcile?book_id=" +
      encodeURIComponent(params.book_id) +
      (params.bank_account_id
        ? "&bank_account_id=" + encodeURIComponent(params.bank_account_id)
        : "");
    downloadExport(url);
  }

  function confirmMatch() {
    var txnId = document.getElementById("manual-txn-id").value || "";
    var voucherId = document.getElementById("manual-voucher-id").value || "";
    var operator = document.getElementById("rec-operator").value || "";
    var role = document.getElementById("rec-role").value || "";
    if (!txnId || !voucherId) {
      setError("请填写流水ID与凭证ID");
      return;
    }

    fetch("/api/reconcile/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User": operator,
        "X-Role": role,
      },
      body: JSON.stringify({ bank_transaction_id: txnId, voucher_id: voucherId }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "确认失败");
          return;
        }
        setError("");
        refresh();
      })
      .catch(function () {
        setError("确认失败");
      });
  }

  function cancelMatch() {
    var txnId = document.getElementById("manual-txn-id").value || "";
    var operator = document.getElementById("rec-operator").value || "";
    var role = document.getElementById("rec-role").value || "";
    if (!txnId) {
      setError("请填写流水ID");
      return;
    }

    fetch("/api/reconcile/cancel", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User": operator,
        "X-Role": role,
      },
      body: JSON.stringify({ bank_transaction_id: txnId }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "取消失败");
          return;
        }
        setError("");
        refresh();
      })
      .catch(function () {
        setError("取消失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("rec-refresh").addEventListener("click", refresh);
    document.getElementById("rec-auto").addEventListener("click", autoMatch);
    document.getElementById("rec-export").addEventListener("click", exportReport);
    document
      .getElementById("manual-confirm")
      .addEventListener("click", confirmMatch);
    document
      .getElementById("manual-cancel")
      .addEventListener("click", cancelMatch);
  });
})();
