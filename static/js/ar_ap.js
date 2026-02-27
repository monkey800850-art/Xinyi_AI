(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(message) {
    var box = document.getElementById("ar-error");
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
        link.download = "ar_ap_aging.xlsx";
        link.click();
        window.URL.revokeObjectURL(link.href);
      })
      .catch(function (err) {
        setError(err.message || "导出失败");
      });
  }
  function fetchSummary() {
    var bookId = document.getElementById("ar-book-id").value || "";
    var asOf = document.getElementById("ar-as-of").value || "";
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }

    var url =
      "/api/ar_ap/summary?book_id=" +
      encodeURIComponent(bookId) +
      (asOf ? "&as_of_date=" + encodeURIComponent(asOf) : "");

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
        document.getElementById("due-soon-count").textContent =
          payload.data.due_soon_count;
        document.getElementById("overdue-count").textContent =
          payload.data.overdue_count;
        document.getElementById("due-soon-amount").textContent = formatAmount(
          payload.data.due_soon_amount
        );
        document.getElementById("overdue-amount").textContent = formatAmount(
          payload.data.overdue_amount
        );
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function fetchWarnings() {
    var bookId = document.getElementById("ar-book-id").value || "";
    var asOf = document.getElementById("ar-as-of").value || "";
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }

    var url =
      "/api/ar_ap/warnings?book_id=" +
      encodeURIComponent(bookId) +
      (asOf ? "&as_of_date=" + encodeURIComponent(asOf) : "");

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
        renderWarnings(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function fetchAging() {
    var bookId = document.getElementById("ar-book-id").value || "";
    var startDate = document.getElementById("ar-start-date").value || "";
    var endDate = document.getElementById("ar-end-date").value || "";
    var asOf = document.getElementById("ar-as-of").value || "";
    if (!bookId || !startDate || !endDate) {
      setError("请填写账套ID与期间");
      return;
    }

    var url =
      "/api/ar_ap/aging?book_id=" +
      encodeURIComponent(bookId) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate) +
      (asOf ? "&as_of_date=" + encodeURIComponent(asOf) : "");

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
        renderAging(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function exportAging() {
    var bookId = document.getElementById("ar-book-id").value || "";
    var startDate = document.getElementById("ar-start-date").value || "";
    var endDate = document.getElementById("ar-end-date").value || "";
    var asOf = document.getElementById("ar-as-of").value || "";
    if (!bookId || !startDate || !endDate) {
      setError("请填写账套ID与期间");
      return;
    }

    var url =
      "/api/exports/ar_ap_aging?book_id=" +
      encodeURIComponent(bookId) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate) +
      (asOf ? "&as_of_date=" + encodeURIComponent(asOf) : "");

    downloadExport(url);
  }

  function renderWarnings(items) {
    var body = document.getElementById("ar-warning-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.voucher_date +
        "</td>" +
        "<td>" +
        item.subject_code +
        " " +
        item.subject_name +
        "</td>" +
        "<td>" +
        (item.counterparty || "") +
        "</td>" +
        "<td>" +
        item.due_date +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.amount) +
        "</td>" +
        "<td>" +
        (item.status === "overdue" ? "逾期" : "临期") +
        "</td>" +
        "<td>" +
        (item.days_overdue || 0) +
        "</td>";
      tr.className = item.status === "overdue" ? "row-overdue" : "row-warning";
      body.appendChild(tr);
    }
  }

  function renderAging(items) {
    var body = document.getElementById("ar-aging-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        (item.counterparty_code || "") +
        " " +
        (item.counterparty_name || "") +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.balance) +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.period_amount) +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.overdue_amount) +
        "</td>" +
        "<td>" +
        (item.overdue_days || 0) +
        "</td>";
      body.appendChild(tr);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document
      .getElementById("ar-refresh")
      .addEventListener("click", fetchSummary);
    document
      .getElementById("ar-query-warning")
      .addEventListener("click", fetchWarnings);
    document
      .getElementById("ar-query-aging")
      .addEventListener("click", fetchAging);
    document
      .getElementById("ar-export-aging")
      .addEventListener("click", exportAging);
  });
})();
