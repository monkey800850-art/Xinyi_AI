(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(message) {
    var box = document.getElementById("aux-error");
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
        link.download = "aux_report.xlsx";
        link.click();
        window.URL.revokeObjectURL(link.href);
      })
      .catch(function (err) {
        setError(err.message || "导出失败");
      });
  }
  function getBookId() {
    return document.getElementById("aux-book-id").value || "";
  }

  function initSubjectAutocomplete() {
    var root = document.getElementById("aux-subject-input").closest(".ac-root");
    new AutocompleteInput(root, {
      type: "subject",
      bookId: parseInt(getBookId() || "1", 10),
      placeholder: "科目编码/名称",
      onSelect: function (item) {
        document.getElementById("aux-subject-input").value = item.display_text;
        document.getElementById("aux-subject-code").value = item.code;
      },
      onChange: function (value) {
        if (!value) {
          document.getElementById("aux-subject-code").value = "";
        }
      },
    });
  }

  function renderAuxInput() {
    var root = document.getElementById("aux-dimension-root");
    root.innerHTML =
      '<input type="text" class="ac-input" id="aux-dimension-input" placeholder="编码/名称" />' +
      '<input type="hidden" id="aux-dimension-code" />' +
      '<div class="ac-dropdown"></div>';

    var type = document.getElementById("aux-type").value;
    new AutocompleteInput(root, {
      type: type,
      bookId: parseInt(getBookId() || "1", 10),
      placeholder: "编码/名称",
      onSelect: function (item) {
        document.getElementById("aux-dimension-input").value = item.display_text;
        document.getElementById("aux-dimension-code").value = item.code;
      },
      onChange: function (value) {
        if (!value) {
          document.getElementById("aux-dimension-code").value = "";
        }
      },
    });
  }

  function renderBalance(items, primary) {
    var body = document.getElementById("aux-balance-body");
    var header = document.getElementById("aux-primary-header");
    header.textContent = primary === "subject" ? "科目" : "辅助项目";
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.primary_code +
        " " +
        item.primary_name +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.period_debit) +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.period_credit) +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.ending_balance) +
        "</td>" +
        '<td><button class="btn small" data-primary-code="' +
        item.primary_code +
        '">明细</button></td>';
      body.appendChild(tr);
    }

    body.addEventListener("click", function (e) {
      var target = e.target;
      if (target && target.matches("button[data-primary-code]")) {
        var primaryCode = target.getAttribute("data-primary-code");
        if (primary === "aux") {
          document.getElementById("aux-dimension-code").value = primaryCode;
        } else {
          document.getElementById("aux-subject-code").value = primaryCode;
        }
        queryLedger();
      }
    });
  }

  function renderLedger(items) {
    var body = document.getElementById("aux-ledger-body");
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
        item.summary +
        "</td>" +
        "<td>" +
        item.subject_code +
        " " +
        item.subject_name +
        "</td>" +
        "<td>" +
        item.aux_code +
        " " +
        item.aux_name +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.debit) +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.credit) +
        "</td>" +
        '<td><button class="btn small" data-voucher-id="' +
        item.voucher_id +
        '">查看</button></td>';
      body.appendChild(tr);
    }

    body.addEventListener("click", function (e) {
      var target = e.target;
      if (target && target.matches("button[data-voucher-id]")) {
        fetchVoucher(target.getAttribute("data-voucher-id"));
      }
    });
  }

  function renderVoucher(detail) {
    var section = document.getElementById("aux-voucher-detail");
    var meta = document.getElementById("aux-voucher-meta");
    var body = document.getElementById("aux-voucher-lines-body");
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

  function queryBalance() {
    var bookId = getBookId();
    var subjectCode = document.getElementById("aux-subject-code").value || "";
    var auxCode = document.getElementById("aux-dimension-code").value || "";
    var auxType = document.getElementById("aux-type").value || "";
    var primary = document.getElementById("aux-primary").value || "aux";
    var startDate = document.getElementById("aux-start-date").value || "";
    var endDate = document.getElementById("aux-end-date").value || "";

    if (!bookId || !auxType || !startDate || !endDate) {
      setError("请填写账套、期间与辅助类型");
      return;
    }

    var url =
      "/api/aux_balance?book_id=" +
      encodeURIComponent(bookId) +
      "&aux_type=" +
      encodeURIComponent(auxType) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate) +
      (subjectCode ? "&subject_code=" + encodeURIComponent(subjectCode) : "") +
      (auxCode ? "&aux_code=" + encodeURIComponent(auxCode) : "") +
      "&primary=" +
      encodeURIComponent(primary);

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
        renderBalance(payload.data.items || [], payload.data.primary);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function queryLedger() {
    var bookId = getBookId();
    var subjectCode = document.getElementById("aux-subject-code").value || "";
    var auxCode = document.getElementById("aux-dimension-code").value || "";
    var auxType = document.getElementById("aux-type").value || "";
    var startDate = document.getElementById("aux-start-date").value || "";
    var endDate = document.getElementById("aux-end-date").value || "";

    if (!bookId || !auxType || !subjectCode || !auxCode || !startDate || !endDate) {
      setError("请填写账套、科目、辅助项目与期间");
      return;
    }

    var url =
      "/api/aux_ledger?book_id=" +
      encodeURIComponent(bookId) +
      "&aux_type=" +
      encodeURIComponent(auxType) +
      "&subject_code=" +
      encodeURIComponent(subjectCode) +
      "&aux_code=" +
      encodeURIComponent(auxCode) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate);

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
        renderLedger(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function exportBalance() {
    var bookId = getBookId();
    var subjectCode = document.getElementById("aux-subject-code").value || "";
    var auxCode = document.getElementById("aux-dimension-code").value || "";
    var auxType = document.getElementById("aux-type").value || "";
    var primary = document.getElementById("aux-primary").value || "aux";
    var startDate = document.getElementById("aux-start-date").value || "";
    var endDate = document.getElementById("aux-end-date").value || "";

    if (!bookId || !auxType || !startDate || !endDate) {
      setError("请填写账套、期间与辅助类型");
      return;
    }

    var url =
      "/api/exports/aux_balance?book_id=" +
      encodeURIComponent(bookId) +
      "&aux_type=" +
      encodeURIComponent(auxType) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate) +
      (subjectCode ? "&subject_code=" + encodeURIComponent(subjectCode) : "") +
      (auxCode ? "&aux_code=" + encodeURIComponent(auxCode) : "") +
      "&primary=" +
      encodeURIComponent(primary);

    downloadExport(url);
  }

  function exportLedger() {
    var bookId = getBookId();
    var subjectCode = document.getElementById("aux-subject-code").value || "";
    var auxCode = document.getElementById("aux-dimension-code").value || "";
    var auxType = document.getElementById("aux-type").value || "";
    var startDate = document.getElementById("aux-start-date").value || "";
    var endDate = document.getElementById("aux-end-date").value || "";

    if (!bookId || !auxType || !subjectCode || !auxCode || !startDate || !endDate) {
      setError("请填写账套、科目、辅助项目与期间");
      return;
    }

    var url =
      "/api/exports/aux_ledger?book_id=" +
      encodeURIComponent(bookId) +
      "&aux_type=" +
      encodeURIComponent(auxType) +
      "&subject_code=" +
      encodeURIComponent(subjectCode) +
      "&aux_code=" +
      encodeURIComponent(auxCode) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate);

    downloadExport(url);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSubjectAutocomplete();
    renderAuxInput();

    document.getElementById("aux-type").addEventListener("change", function () {
      renderAuxInput();
    });

    document
      .getElementById("aux-query-balance")
      .addEventListener("click", queryBalance);
    document
      .getElementById("aux-query-ledger")
      .addEventListener("click", queryLedger);
    document
      .getElementById("aux-export-balance")
      .addEventListener("click", exportBalance);
    document
      .getElementById("aux-export-ledger")
      .addEventListener("click", exportLedger);
  });
})();
