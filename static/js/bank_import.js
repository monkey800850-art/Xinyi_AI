(function () {
  function formatAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return "0.00";
    }
    return num.toFixed(2);
  }

  function setError(message) {
    var box = document.getElementById("bank-error");
    if (!box) return;
    if (!message) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    box.classList.remove("hidden");
    box.textContent = message;
  }

  function setResult(data) {
    var box = document.getElementById("bank-result");
    if (!box) return;
    if (!data) {
      box.classList.add("hidden");
      box.textContent = "";
      return;
    }
    box.classList.remove("hidden");
    box.textContent =
      "总数：" +
      data.total +
      "，成功：" +
      data.success +
      "，失败：" +
      data.failed +
      "，重复：" +
      data.duplicated +
      (data.errors && data.errors.length
        ? "（错误行数：" + data.errors.length + "）"
        : "");
  }

  function renderList(items) {
    var body = document.getElementById("bank-body");
    body.innerHTML = "";
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        item.id +
        "</td>" +
        "<td>" +
        item.bank_account_id +
        "</td>" +
        "<td>" +
        item.txn_date +
        "</td>" +
        "<td class=\"amount\">" +
        formatAmount(item.amount) +
        "</td>" +
        "<td>" +
        (item.summary || "") +
        "</td>" +
        "<td>" +
        (item.counterparty || "") +
        "</td>" +
        "<td class=\"amount\">" +
        (item.balance === null ? "" : formatAmount(item.balance)) +
        "</td>" +
        "<td>" +
        (item.serial_no || "") +
        "</td>";
      body.appendChild(tr);
    }
  }

  function refreshList() {
    var bookId = document.getElementById("bank-book-id").value || "";
    var accountId = document.getElementById("bank-account-id").value || "";
    if (!bookId) {
      setError("请填写账套ID");
      return;
    }
    var url =
      "/api/bank_transactions?book_id=" +
      encodeURIComponent(bookId) +
      (accountId ? "&bank_account_id=" + encodeURIComponent(accountId) : "");

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
        renderList(payload.data.items || []);
      })
      .catch(function () {
        setError("查询失败");
      });
  }

  function doImport() {
    var bookId = document.getElementById("bank-book-id").value || "";
    var accountId = document.getElementById("bank-account-id").value || "";
    var fileInput = document.getElementById("bank-file");
    var file = fileInput.files[0];

    if (!bookId || !accountId || !file) {
      setError("请填写账套ID、银行账户ID并选择文件");
      return;
    }

    var form = new FormData();
    form.append("book_id", bookId);
    form.append("bank_account_id", accountId);
    form.append("file", file);

    fetch("/api/bank_transactions/import", {
      method: "POST",
      body: form,
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          setError(payload.data.error || "导入失败");
          setResult(null);
          return;
        }
        setError("");
        setResult(payload.data);
        refreshList();
      })
      .catch(function () {
        setError("导入失败");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("bank-import").addEventListener("click", doImport);
    document.getElementById("bank-refresh").addEventListener("click", refreshList);
  });
})();
