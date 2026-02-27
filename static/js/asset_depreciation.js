(function () {
  function setError(message, errors) {
    var box = document.getElementById("dep-error");
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
        var code = item.asset_code ? "资产" + item.asset_code + "：" : "";
        var field = item.field ? item.field + "：" : "";
        lines.push(code + field + item.message);
      }
    }
    box.textContent = lines.join("\n");
    box.classList.remove("hidden");
  }

  function fetchJson(url, options) {
    return fetch(url, options).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    });
  }

  function getParams() {
    return {
      book_id: document.getElementById("dep-book-id").value,
      year: document.getElementById("dep-year").value,
      month: document.getElementById("dep-month").value,
    };
  }

  function renderPreview(result) {
    var body = document.getElementById("dep-preview-body");
    body.innerHTML = "";
    var items = result.items || [];
    if (items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="4">暂无数据</td>';
      body.appendChild(empty);
    } else {
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          item.asset_code +
          "</td><td>" +
          item.asset_name +
          "</td><td>" +
          item.amount +
          "</td><td>" +
          item.status +
          "</td>";
        body.appendChild(tr);
      }
    }
    var summary = document.getElementById("dep-summary");
    summary.textContent =
      "期间：" +
      result.period_year +
      "-" +
      String(result.period_month).padStart(2, "0") +
      "，合计：" +
      result.total_amount;
  }

  function preview() {
    var params = getParams();
    fetchJson(
      "/api/assets/depreciation/preview?book_id=" +
        encodeURIComponent(params.book_id) +
        "&year=" +
        encodeURIComponent(params.year) +
        "&month=" +
        encodeURIComponent(params.month)
    )
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "试算失败", payload.data.errors);
          return;
        }
        setError("", []);
        renderPreview(payload.data);
      })
      .catch(function () {
        setError("试算失败");
      });
  }

  function runDepreciation() {
    var params = getParams();
    params.voucher_status = document.getElementById("dep-voucher-status").value;
    fetchJson("/api/assets/depreciation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "计提失败", payload.data.errors);
          return;
        }
        setError("计提成功，批次ID：" + payload.data.batch_id, []);
        listBatches();
      })
      .catch(function () {
        setError("计提失败");
      });
  }

  function renderBatches(items) {
    var body = document.getElementById("dep-batch-body");
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="5">暂无批次</td>';
      body.appendChild(empty);
      return;
    }
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.period_year +
        "-" +
        String(item.period_month).padStart(2, "0") +
        "</td><td>" +
        item.status +
        "</td><td>" +
        item.total_amount +
        "</td><td>" +
        (item.voucher_id || "") +
        "</td><td>" +
        '<button class="btn small" data-batch-id="' +
        item.id +
        '">查看</button>' +
        "</td>";
      body.appendChild(tr);
    }
  }

  function listBatches() {
    var bookId = document.getElementById("dep-book-id").value || "";
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }
    fetchJson("/api/assets/depreciation?book_id=" + encodeURIComponent(bookId))
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "查询失败", payload.data.errors);
          return;
        }
        setError("", []);
        renderBatches(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function renderDetail(result) {
    var title = document.getElementById("dep-detail-title");
    title.textContent =
      "批次：" +
      result.period_year +
      "-" +
      String(result.period_month).padStart(2, "0") +
      "，合计：" +
      result.total_amount;

    var body = document.getElementById("dep-detail-body");
    body.innerHTML = "";
    var items = result.items || [];
    if (items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="4">暂无明细</td>';
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
        item.amount +
        "</td><td>" +
        item.status +
        "</td>";
      body.appendChild(tr);
    }
  }

  function loadBatchDetail(batchId) {
    fetchJson("/api/assets/depreciation/" + batchId)
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "加载失败", payload.data.errors);
          return;
        }
        setError("", []);
        renderDetail(payload.data);
      })
      .catch(function () {
        setError("加载失败");
      });
  }

  document.addEventListener("click", function (e) {
    if (e.target && e.target.matches("button[data-batch-id]")) {
      var id = e.target.getAttribute("data-batch-id");
      loadBatchDetail(id);
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("dep-preview").addEventListener("click", preview);
    document.getElementById("dep-run").addEventListener("click", runDepreciation);
    document.getElementById("dep-refresh").addEventListener("click", listBatches);
    listBatches();
  });
})();
