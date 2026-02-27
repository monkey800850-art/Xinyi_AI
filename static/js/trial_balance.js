(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(message) {
    var box = document.getElementById("tb-error");
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

  function buildRow(item, hasChildren) {
    var tr = document.createElement("tr");
    tr.dataset.code = item.code;
    tr.dataset.parent = item.parent_code || "";
    tr.dataset.level = item.level;
    tr.dataset.expanded = "true";

    var subjectCell = document.createElement("td");
    subjectCell.className = "col-subject";

    var indent = document.createElement("span");
    indent.className = "indent";
    indent.style.width = (item.level - 1) * 16 + "px";

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "toggle";
    toggle.textContent = hasChildren ? "-" : "";
    toggle.disabled = !hasChildren;

    var label = document.createElement("span");
    label.className = "label";
    label.textContent = item.code + " " + item.name;

    subjectCell.appendChild(indent);
    subjectCell.appendChild(toggle);
    subjectCell.appendChild(label);

    tr.appendChild(subjectCell);
    tr.appendChild(amountCell(item.opening_balance));
    tr.appendChild(amountCell(item.period_debit));
    tr.appendChild(amountCell(item.period_credit));
    tr.appendChild(amountCell(item.ending_balance));

    toggle.addEventListener("click", function () {
      var expanded = tr.dataset.expanded === "true";
      tr.dataset.expanded = expanded ? "false" : "true";
      toggle.textContent = expanded ? "+" : "-";
      toggleChildren(item.code, !expanded);
    });

    return tr;
  }

  function amountCell(value) {
    var td = document.createElement("td");
    td.className = "col-amount";
    td.textContent = formatAmount(value);
    return td;
  }

  function toggleChildren(parentCode, show) {
    var rows = document.querySelectorAll("#tb-body tr");
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (row.dataset.parent === parentCode) {
        row.style.display = show ? "" : "none";
        if (!show) {
          row.dataset.expanded = "false";
          var toggle = row.querySelector(".toggle");
          if (toggle && toggle.textContent) {
            toggle.textContent = "+";
          }
          toggleChildren(row.dataset.code, false);
        }
      }
    }
  }

  function render(items) {
    var body = document.getElementById("tb-body");
    body.innerHTML = "";

    var childrenMap = {};
    for (var i = 0; i < items.length; i++) {
      var p = items[i].parent_code || "";
      if (!childrenMap[p]) {
        childrenMap[p] = [];
      }
      childrenMap[p].push(items[i].code);
    }

    for (var j = 0; j < items.length; j++) {
      var item = items[j];
      var hasChildren = !!childrenMap[item.code];
      var row = buildRow(item, hasChildren);
      body.appendChild(row);
    }
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
        link.download = "trial_balance.xlsx";
        link.click();
        window.URL.revokeObjectURL(link.href);
      })
      .catch(function (err) {
        setError(err.message || "导出失败");
      });
  }

  function query() {
    var bookId = document.getElementById("tb-book-id").value || "";
    var startDate = document.getElementById("tb-start-date").value || "";
    var endDate = document.getElementById("tb-end-date").value || "";

    if (!bookId || !startDate || !endDate) {
      setError("请填写账套ID与起止日期");
      return;
    }

    var url =
      "/api/trial_balance?book_id=" +
      encodeURIComponent(bookId) +
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
        render(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function exportExcel() {
    var bookId = document.getElementById("tb-book-id").value || "";
    var startDate = document.getElementById("tb-start-date").value || "";
    var endDate = document.getElementById("tb-end-date").value || "";

    if (!bookId || !startDate || !endDate) {
      setError("请填写账套ID与起止日期");
      return;
    }

    var url =
      "/api/exports/trial_balance?book_id=" +
      encodeURIComponent(bookId) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate);
    downloadExport(url);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("tb-query-btn").addEventListener("click", query);
    document.getElementById("tb-export-btn").addEventListener("click", exportExcel);
  });
})();
