(function () {
  function setError(message, errors) {
    var box = document.getElementById("report-error");
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

  function downloadExport(url, name) {
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
        link.download = name;
        link.click();
        window.URL.revokeObjectURL(link.href);
      })
      .catch(function (err) {
        setError(err.message || "导出失败");
      });
  }
  function fetchJson(url) {
    return fetch(url).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    });
  }

  function renderDetail(items) {
    var body = document.getElementById("report-detail-body");
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="8">暂无数据</td>';
      body.appendChild(empty);
      return;
    }
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.asset_code +
        "</td><td>" +
        item.asset_name +
        "</td><td>" +
        item.period +
        "</td><td>" +
        item.amount +
        "</td><td>" +
        item.accumulated_depr +
        "</td><td>" +
        item.net_value +
        "</td><td>" +
        item.batch_id +
        "</td><td>" +
        (item.voucher_id || "") +
        "</td>";
      body.appendChild(tr);
    }
  }

  function renderSummary(tableId, items, fieldKey) {
    var body = document.getElementById(tableId);
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="2">暂无数据</td>';
      body.appendChild(empty);
      return;
    }
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        (item[fieldKey] || "") +
        "</td><td>" +
        item.total_amount +
        "</td>";
      body.appendChild(tr);
    }
  }

  function buildQuery() {
    var keyword = document.getElementById("report-keyword").value || "";
    var assetCode = "";
    var assetName = "";
    if (keyword) {
      assetCode = keyword;
      assetName = keyword;
    }
    return (
      "book_id=" +
      encodeURIComponent(document.getElementById("report-book-id").value || "") +
      "&year=" +
      encodeURIComponent(document.getElementById("report-year").value || "") +
      "&month=" +
      encodeURIComponent(document.getElementById("report-month").value || "") +
      "&asset_code=" +
      encodeURIComponent(assetCode) +
      "&asset_name=" +
      encodeURIComponent(assetName) +
      "&category_id=" +
      encodeURIComponent(document.getElementById("report-category-id").value || "")
    );
  }

  function search() {
    var query = buildQuery();
    fetchJson("/api/assets/depreciation/detail?" + query)
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "查询失败", payload.data.errors);
          return;
        }
        setError("", []);
        renderDetail(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });

    fetchJson("/api/assets/depreciation/summary?" + query)
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "查询失败", payload.data.errors);
          return;
        }
        renderSummary("report-category-body", payload.data.by_category || [], "category_name");
        renderSummary("report-dept-body", payload.data.by_department || [], "department_name");
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function exportDetail() {
    var query = buildQuery();
    var url = "/api/exports/assets/depreciation_detail?" + query;
    downloadExport(url, "asset_depreciation_detail.xlsx");
  }

  function exportSummary() {
    var query = buildQuery();
    var url = "/api/exports/assets/depreciation_summary?" + query;
    downloadExport(url, "asset_depreciation_summary.xlsx");
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("report-search").addEventListener("click", search);
    document.getElementById("report-export-detail").addEventListener("click", exportDetail);
    document.getElementById("report-export-summary").addEventListener("click", exportSummary);
  });
})();
