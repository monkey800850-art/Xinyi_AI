(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(message) {
    var box = document.getElementById("tax-summary-error");
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
        link.download = "tax_summary.xlsx";
        link.click();
        window.URL.revokeObjectURL(link.href);
      })
      .catch(function (err) {
        setError(err.message || "导出失败");
      });
  }
  function renderSummary(items) {
    var body = document.getElementById("tax-summary-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        (item.category || "") +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.total_amount) +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.total_tax) +
        "</td>";
      body.appendChild(tr);
    }
  }

  function renderValidate(items) {
    var body = document.getElementById("tax-validate-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML = "<td>" + item.id + "</td><td>" + item.message + "</td>";
      body.appendChild(tr);
    }
  }

  function renderAlerts(items) {
    var body = document.getElementById("tax-alert-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.severity +
        "</td>" +
        "<td>" +
        item.alert_type +
        "</td>" +
        "<td>" +
        item.message +
        "</td>" +
        "<td>" +
        (item.ref_id || "") +
        "</td>";
      body.appendChild(tr);
    }
  }

  function getBookId() {
    return document.getElementById("tax-book-id").value || "";
  }

  function fetchSummary() {
    var bookId = getBookId();
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }
    var url = "/api/tax/summary?book_id=" + encodeURIComponent(bookId);
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
        renderSummary(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function fetchValidate() {
    var bookId = getBookId();
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }
    var url = "/api/tax/validate?book_id=" + encodeURIComponent(bookId);
    fetch(url)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "校验失败");
          return;
        }
        setError("");
        renderValidate(payload.data.errors || []);
      })
      .catch(function () {
        setError("校验失败");
      });
  }

  function fetchAlerts() {
    var bookId = getBookId();
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }
    var url = "/api/tax/alerts/build?book_id=" + encodeURIComponent(bookId);
    fetch(url)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "预警失败");
          return;
        }
        setError("");
        renderAlerts(payload.data.items || []);
      })
      .catch(function () {
        setError("预警失败");
      });
  }

  function exportSummary() {
    var bookId = getBookId();
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }
    var url = "/api/exports/tax_summary?book_id=" + encodeURIComponent(bookId);
    downloadExport(url);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("tax-summary").addEventListener("click", fetchSummary);
    document.getElementById("tax-validate").addEventListener("click", fetchValidate);
    document.getElementById("tax-alerts").addEventListener("click", fetchAlerts);
    document.getElementById("tax-export").addEventListener("click", exportSummary);
  });
})();
