(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(message) {
    var box = document.getElementById("ledger-error");
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
        link.download = "subject_ledger.xlsx";
        link.click();
        window.URL.revokeObjectURL(link.href);
      })
      .catch(function (err) {
        setError(err.message || "导出失败");
      });
  }
  function renderRows(items) {
    var body = document.getElementById("ledger-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.voucher_date +
        "</td>" +
        "<td>" +
        item.voucher_word +
        item.voucher_no +
        "</td>" +
        "<td>" +
        item.line_no +
        "</td>" +
        "<td>" +
        item.summary +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.debit) +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.credit) +
        "</td>" +
        "<td>" +
        item.note +
        "</td>" +
        '<td><button class="btn small" data-voucher-id="' +
        item.voucher_id +
        '">查看</button></td>';
      body.appendChild(tr);
    }
  }

  function renderVoucher(detail) {
    var section = document.getElementById("voucher-detail");
    var meta = document.getElementById("voucher-meta");
    var body = document.getElementById("voucher-lines-body");
    section.style.display = "block";

    meta.textContent =
      "凭证ID：" +
      detail.id +
      " | 日期：" +
      detail.voucher_date +
      " | 凭证号：" +
      detail.voucher_word +
      detail.voucher_no +
      " | 状态：" +
      detail.status;

    body.innerHTML = "";
    for (var i = 0; i < detail.lines.length; i++) {
      var line = detail.lines[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        line.line_no +
        "</td>" +
        "<td>" +
        line.summary +
        "</td>" +
        "<td>" +
        line.subject_code +
        " " +
        line.subject_name +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(line.debit) +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(line.credit) +
        "</td>" +
        "<td>" +
        (line.due_date || "") +
        "</td>" +
        "<td>" +
        line.note +
        "</td>";
      body.appendChild(tr);
    }
  }

  function fetchVoucher(voucherId) {
    fetch("/api/vouchers/" + voucherId)
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
        renderVoucher(payload.data);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function query() {
    var bookId = document.getElementById("ledger-book-id").value || "";
    var subjectCode = document.getElementById("ledger-subject-code").value || "";
    var startDate = document.getElementById("ledger-start-date").value || "";
    var endDate = document.getElementById("ledger-end-date").value || "";
    var summary = document.getElementById("ledger-summary").value || "";
    var direction = document.getElementById("ledger-direction").value || "";

    if (!bookId || !subjectCode || !startDate || !endDate) {
      setError("请填写账套ID、科目编码与期间");
      return;
    }

    var url =
      "/api/subject_ledger?book_id=" +
      encodeURIComponent(bookId) +
      "&subject_code=" +
      encodeURIComponent(subjectCode) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate) +
      (summary ? "&summary=" + encodeURIComponent(summary) : "") +
      (direction ? "&direction=" + encodeURIComponent(direction) : "");

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
        document.getElementById("ledger-title").textContent =
          payload.data.subject_code + " " + payload.data.subject_name;
        renderRows(payload.data.items || []);

        var body = document.getElementById("ledger-body");
        body.addEventListener("click", function (e) {
          var target = e.target;
          if (target && target.matches("button[data-voucher-id]")) {
            fetchVoucher(target.getAttribute("data-voucher-id"));
          }
        });
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function exportLedger() {
    var bookId = document.getElementById("ledger-book-id").value || "";
    var subjectCode = document.getElementById("ledger-subject-code").value || "";
    var startDate = document.getElementById("ledger-start-date").value || "";
    var endDate = document.getElementById("ledger-end-date").value || "";
    var summary = document.getElementById("ledger-summary").value || "";
    var direction = document.getElementById("ledger-direction").value || "";

    if (!bookId || !subjectCode || !startDate || !endDate) {
      setError("请填写账套ID、科目编码与期间");
      return;
    }

    var url =
      "/api/exports/subject_ledger?book_id=" +
      encodeURIComponent(bookId) +
      "&subject_code=" +
      encodeURIComponent(subjectCode) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate) +
      (summary ? "&summary=" + encodeURIComponent(summary) : "") +
      (direction ? "&direction=" + encodeURIComponent(direction) : "");

    downloadExport(url);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("ledger-query-btn").addEventListener("click", query);
    document
      .getElementById("ledger-export-btn")
      .addEventListener("click", exportLedger);
  });
})();
