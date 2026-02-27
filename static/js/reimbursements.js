(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(id, message) {
    var box = document.getElementById(id);
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

  function qs(id) {
    return document.getElementById(id);
  }

  function collectItems() {
    var rows = document.querySelectorAll("#items-body tr");
    var items = [];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      items.push({
        expense_date: row.querySelector(".item-date")?.value || "",
        category: row.querySelector(".item-category")?.value || "",
        description: row.querySelector(".item-desc")?.value || "",
        amount: row.querySelector(".item-amount")?.value || "",
      });
    }
    return items;
  }

  function renderLogs(logs) {
    var body = qs("logs-body");
    if (!body) return;
    body.innerHTML = "";
    for (var i = 0; i < logs.length; i++) {
      var l = logs[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        l.action +
        "</td>" +
        "<td>" +
        l.from_status +
        " → " +
        l.to_status +
        "</td>" +
        "<td>" +
        l.operator +
        "</td>" +
        "<td>" +
        l.operator_role +
        "</td>" +
        "<td>" +
        (l.comment || "") +
        "</td>" +
        "<td>" +
        l.created_at +
        "</td>";
      body.appendChild(tr);
    }
  }

  function renderList(items) {
    var body = qs("reim-body");
    if (!body) return;
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.id +
        "</td>" +
        "<td>" +
        item.title +
        "</td>" +
        "<td>" +
        item.applicant +
        "</td>" +
        "<td>" +
        item.department +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.total_amount) +
        "</td>" +
        "<td>" +
        item.status +
        "</td>" +
        "<td>" +
        (item.reject_reason || "") +
        "</td>" +
        '<td><a class="btn small" href="/reimbursements/' +
        item.id +
        '">查看</a></td>';
      body.appendChild(tr);
    }
  }

  function renderStats(items) {
    var body = qs("reim-stats-body");
    if (!body) return;
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.status +
        "</td>" +
        "<td>" +
        item.count +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.amount) +
        "</td>";
      body.appendChild(tr);
    }
  }

  function listReimbursements() {
    var bookId = qs("reim-book-id").value || "";
    var status = qs("reim-status").value || "";
    if (!bookId) {
      setError("reim-error", "请填写账套ID");
      return;
    }

    var url =
      "/api/reimbursements?book_id=" +
      encodeURIComponent(bookId) +
      (status ? "&status=" + encodeURIComponent(status) : "");

    fetch(url)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("reim-error", payload.data.error || "查询失败");
          return;
        }
        setError("reim-error", "");
        renderList(payload.data.items || []);
      })
      .catch(function () {
        setError("reim-error", "查询失败");
      });
  }

  function statsReimbursements() {
    var bookId = qs("reim-book-id").value || "";
    if (!bookId) {
      setError("reim-error", "请填写账套ID");
      return;
    }

    var url = "/api/reimbursements/stats?book_id=" + encodeURIComponent(bookId);
    fetch(url)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("reim-error", payload.data.error || "查询失败");
          return;
        }
        setError("reim-error", "");
        renderStats(payload.data.items || []);
      })
      .catch(function () {
        setError("reim-error", "查询失败");
      });
  }

  function saveDetail() {
    var payload = {
      id: qs("detail-id")?.value || "",
      book_id: qs("detail-book-id").value,
      title: qs("detail-title").value,
      applicant: qs("detail-applicant").value,
      department: qs("detail-department").value,
      attachment_count: qs("detail-attachment-count").value,
      status: "draft",
      items: collectItems(),
    };

    fetch("/api/reimbursements", {
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
          setError("detail-error", payload.data.error || "保存失败");
          return;
        }
        setError("detail-error", "");
        window.location.href = "/reimbursements/" + payload.data.id;
      })
      .catch(function () {
        setError("detail-error", "保存失败");
      });
  }

  function submitDetail() {
    var id = qs("detail-id").value;
    var operator = qs("detail-operator").value || "";
    var role = qs("detail-role").value || "";

    fetch("/api/reimbursements/" + id + "/submit", {
      method: "POST",
      headers: {
        "X-User": operator,
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
          setError("detail-error", payload.data.error || "提交失败");
          return;
        }
        setError("detail-error", "");
        window.location.reload();
      })
      .catch(function () {
        setError("detail-error", "提交失败");
      });
  }

  function approveDetail(approve, reason) {
    var id = qs("detail-id").value;
    var operator = qs("detail-operator").value || "";
    var role = qs("detail-role").value || "";
    var url =
      "/api/reimbursements/" + id + (approve ? "/approve" : "/reject");

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User": operator,
        "X-Role": role,
      },
      body: approve ? JSON.stringify({ comment: reason || "" }) : JSON.stringify({ reason: reason || "" }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("detail-error", payload.data.error || "审批失败");
          return;
        }
        setError("detail-error", "");
        window.location.reload();
      })
      .catch(function () {
        setError("detail-error", "审批失败");
      });
  }

  function loadDetail() {
    var id = qs("detail-id");
    if (!id) return;
    var rid = id.value;
    if (!rid) return;

    fetch("/api/reimbursements/" + rid)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError("detail-error", payload.data.error || "加载失败");
          return;
        }
        var data = payload.data;
        qs("detail-title").value = data.title;
        qs("detail-applicant").value = data.applicant;
        qs("detail-department").value = data.department;
        qs("detail-attachment-count").value = data.attachment_count;
        qs("detail-status").textContent = data.status;
        qs("detail-reject-reason").textContent = data.reject_reason || "-";
        renderLogs(data.logs || []);

        var body = qs("items-body");
        body.innerHTML = "";
        for (var i = 0; i < data.items.length; i++) {
          var item = data.items[i];
          var tr = document.createElement("tr");
          tr.innerHTML =
            "<td><input type=\"date\" class=\"item-date\" value=\"" +
            item.expense_date +
            "\"></td>" +
            "<td><input type=\"text\" class=\"item-category\" value=\"" +
            item.category +
            "\"></td>" +
            "<td><input type=\"text\" class=\"item-desc\" value=\"" +
            item.description +
            "\"></td>" +
            "<td><input type=\"number\" class=\"item-amount\" step=\"0.01\" value=\"" +
            item.amount +
            "\"></td>" +
            '<td><button class="btn small item-remove">删除</button></td>';
          body.appendChild(tr);
        }
      })
      .catch(function () {
        setError("detail-error", "加载失败");
      });
  }

  function addItemRow() {
    var body = qs("items-body");
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td><input type=\"date\" class=\"item-date\"></td>" +
      "<td><input type=\"text\" class=\"item-category\"></td>" +
      "<td><input type=\"text\" class=\"item-desc\"></td>" +
      "<td><input type=\"number\" class=\"item-amount\" step=\"0.01\"></td>" +
      '<td><button class="btn small item-remove">删除</button></td>';
    body.appendChild(tr);
  }

  document.addEventListener("click", function (e) {
    if (e.target && e.target.classList.contains("item-remove")) {
      e.target.closest("tr").remove();
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (qs("reim-query")) {
      qs("reim-query").addEventListener("click", listReimbursements);
      qs("reim-stats").addEventListener("click", statsReimbursements);
      listReimbursements();
    }

    if (qs("detail-save")) {
      qs("detail-save").addEventListener("click", saveDetail);
      qs("detail-submit").addEventListener("click", submitDetail);
      qs("detail-approve").addEventListener("click", function () {
        approveDetail(true, prompt("审批意见（可空）") || "");
      });
      qs("detail-reject").addEventListener("click", function () {
        var reason = prompt("驳回原因（必填）") || "";
        approveDetail(false, reason);
      });
      qs("item-add").addEventListener("click", addItemRow);
      loadDetail();
    }
  });
})();
