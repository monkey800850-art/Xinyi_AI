(function () {
  function setError(message) {
    var box = document.getElementById("boss-error");
    if (!box) return;
    if (!message) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    box.classList.remove("hidden");
    box.textContent = message;
  }

  function renderCards(items) {
    var box = document.getElementById("boss-cards");
    box.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var div = document.createElement("div");
      div.className = "metric-card";
      div.innerHTML =
        "<div class=\"label\">" +
        item.label +
        "</div>" +
        "<div class=\"value\">" +
        item.value +
        "</div>";
      box.appendChild(div);
    }
  }

  function renderRisk(items) {
    var box = document.getElementById("boss-risk");
    box.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var div = document.createElement("div");
      div.className = "metric-card warning";
      div.innerHTML =
        "<div class=\"label\">" +
        item.label +
        "</div>" +
        "<div class=\"value\">" +
        item.value +
        "</div>";
      box.appendChild(div);
    }
  }

  function drawTrend(points) {
    var canvas = document.getElementById("boss-trend");
    var ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!points || points.length === 0) {
      ctx.fillStyle = "#667085";
      ctx.fillText("暂无趋势数据", 10, 20);
      return;
    }

    var values = points.map(function (p) {
      return p.value;
    });
    var max = Math.max.apply(null, values);
    var min = Math.min.apply(null, values);
    var padding = 20;
    var w = canvas.width - padding * 2;
    var h = canvas.height - padding * 2;

    ctx.strokeStyle = "#1570ef";
    ctx.lineWidth = 2;
    ctx.beginPath();

    for (var i = 0; i < points.length; i++) {
      var x = padding + (w * i) / (points.length - 1 || 1);
      var ratio = max === min ? 0.5 : (points[i].value - min) / (max - min);
      var y = padding + h - ratio * h;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();
  }

  function refresh() {
    var bookId = document.getElementById("boss-book-id").value || "";
    var startDate = document.getElementById("boss-start-date").value || "";
    var endDate = document.getElementById("boss-end-date").value || "";
    var role = document.getElementById("boss-role").value || "boss";
    if (!bookId || !startDate || !endDate) {
      setError("请填写账套ID与起止日期");
      return;
    }

    var url =
      "/api/dashboard/boss?book_id=" +
      encodeURIComponent(bookId) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate);

    fetch(url, {
      headers: {
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
          setError(payload.data.error || "查询失败");
          return;
        }
        setError("");
        var data = payload.data;
        renderCards([
          { label: "资金状况", value: data.cash.toFixed(2) },
          { label: "资产", value: data.assets.toFixed(2) },
          { label: "负债", value: data.liabilities.toFixed(2) },
          { label: "利润", value: data.profit.toFixed(2) },
          { label: "应收应付临期", value: data.arap_due_soon },
          { label: "应收应付逾期", value: data.arap_overdue },
        ]);
        renderRisk([
          { label: "逾期风险", value: data.risk.arap_overdue },
        ]);
        drawTrend(data.trend || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("boss-refresh").addEventListener("click", refresh);
  });
})();
