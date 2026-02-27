(function () {
  function setError(message) {
    var box = document.getElementById("tax-error");
    if (!box) return;
    if (!message) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    box.classList.remove("hidden");
    box.textContent = message;
  }

  function renderRules(items) {
    var body = document.getElementById("rule-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var r = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        r.id +
        "</td>" +
        "<td>" +
        r.region +
        "</td>" +
        "<td>" +
        r.tax_type +
        "</td>" +
        "<td>" +
        r.rate +
        "</td>" +
        "<td>" +
        (r.reduction_type || "") +
        "</td>" +
        "<td>" +
        (r.reduction_rate === null ? "" : r.reduction_rate) +
        "</td>" +
        "<td>" +
        (r.note || "") +
        "</td>" +
        "<td>" +
        r.is_enabled +
        "</td>";
      body.appendChild(tr);
    }
  }

  function listRules() {
    fetch("/api/tax/rules")
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
        renderRules(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function addRule() {
    var payload = {
      region: document.getElementById("rule-region").value,
      tax_type: document.getElementById("rule-type").value,
      rate: document.getElementById("rule-rate").value,
      reduction_type: document.getElementById("rule-reduction-type").value,
      reduction_rate: document.getElementById("rule-reduction-rate").value,
      note: document.getElementById("rule-note").value,
      is_enabled: 1,
    };

    fetch("/api/tax/rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "新增失败");
          return;
        }
        setError("");
        listRules();
      })
      .catch(function () {
        setError("新增失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("rule-add").addEventListener("click", addRule);
    listRules();
  });
})();
