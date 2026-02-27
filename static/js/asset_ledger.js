(function () {
  function setError(message, errors) {
    var box = document.getElementById("ledger-error");
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
        link.download = "asset_ledger.xlsx";
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

  function render(items) {
    var body = document.getElementById("ledger-body");
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="9">暂无数据</td>';
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
        (item.category_name || "") +
        "</td><td>" +
        item.original_value +
        "</td><td>" +
        item.accumulated_depr +
        "</td><td>" +
        item.net_value +
        "</td><td>" +
        item.status +
        "</td><td>" +
        (item.department_name || "") +
        "</td><td>" +
        (item.start_use_date || "") +
        "</td>";
      body.appendChild(tr);
    }
  }

  function buildQuery() {
    var keyword = document.getElementById("ledger-keyword").value || "";
    var assetCode = "";
    var assetName = "";
    if (keyword) {
      assetCode = keyword;
      assetName = keyword;
    }

    var params = {
      book_id: document.getElementById("ledger-book-id").value,
      asset_code: assetCode,
      asset_name: assetName,
      category_id: document.getElementById("ledger-category-id").value,
      status: document.getElementById("ledger-status").value,
      department_id: document.getElementById("ledger-dept-id").value,
      start_use_from: document.getElementById("ledger-start-from").value,
      start_use_to: document.getElementById("ledger-start-to").value,
      dep_year: document.getElementById("ledger-dep-year").value,
      dep_month: document.getElementById("ledger-dep-month").value,
    };

    var query = Object.keys(params)
      .map(function (key) {
        return key + "=" + encodeURIComponent(params[key] || "");
      })
      .join("&");
    return "/api/assets/ledger?" + query;
  }

  function search() {
    var url = buildQuery();
    fetchJson(url)
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "查询失败", payload.data.errors);
          return;
        }
        setError("", []);
        render(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function exportLedger() {
    var url = buildQuery().replace("/api/assets/ledger", "/api/exports/assets/ledger");
    downloadExport(url);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("ledger-search").addEventListener("click", search);
    document.getElementById("ledger-export").addEventListener("click", exportLedger);
  });
})();
