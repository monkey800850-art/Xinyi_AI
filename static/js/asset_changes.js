(function () {
  function setError(message, errors) {
    var box = document.getElementById("change-error");
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

  function fetchJson(url) {
    return fetch(url).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    });
  }

  function render(items) {
    var body = document.getElementById("change-body");
    body.innerHTML = "";
    if (!items || items.length === 0) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="9">暂无记录</td>';
      body.appendChild(empty);
      return;
    }

    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.change_date +
        "</td><td>" +
        item.asset_code +
        "</td><td>" +
        item.change_type +
        "</td><td>" +
        (item.from_department_id || "") +
        "</td><td>" +
        (item.to_department_id || "") +
        "</td><td>" +
        (item.from_person_id || "") +
        "</td><td>" +
        (item.to_person_id || "") +
        "</td><td>" +
        (item.note || "") +
        "</td><td>" +
        (item.operator || "") +
        "</td>";
      body.appendChild(tr);
    }
  }

  function listChanges() {
    var bookId = document.getElementById("change-book-id").value || "";
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }

    var type = document.getElementById("change-type").value;
    var startDate = document.getElementById("change-start").value;
    var endDate = document.getElementById("change-end").value;

    var url =
      "/api/assets/changes?book_id=" +
      encodeURIComponent(bookId) +
      "&change_type=" +
      encodeURIComponent(type) +
      "&start_date=" +
      encodeURIComponent(startDate) +
      "&end_date=" +
      encodeURIComponent(endDate);

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

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("change-refresh").addEventListener("click", listChanges);
    listChanges();
  });
})();
