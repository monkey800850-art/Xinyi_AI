(function () {
  function getBookId() {
    var raw = document.body.getAttribute("data-book-id");
    var val = parseInt(raw, 10);
    if (!val || val <= 0) {
      return 1;
    }
    return val;
  }

  function formatAmount(value) {
    return value.toFixed(2);
  }

  function parseAmount(value) {
    var num = parseFloat(value);
    if (isNaN(num)) {
      return 0;
    }
    return num;
  }

  function recalcTotals() {
    var debitInputs = document.querySelectorAll(".debit-input");
    var creditInputs = document.querySelectorAll(".credit-input");
    var debitTotal = 0;
    var creditTotal = 0;

    for (var i = 0; i < debitInputs.length; i++) {
      debitTotal += parseAmount(debitInputs[i].value);
    }
    for (var j = 0; j < creditInputs.length; j++) {
      creditTotal += parseAmount(creditInputs[j].value);
    }

    var diff = debitTotal - creditTotal;

    document.getElementById("debit-total").textContent = formatAmount(debitTotal);
    document.getElementById("credit-total").textContent = formatAmount(creditTotal);
    document.getElementById("diff-total").textContent = formatAmount(diff);
  }

  function bindAmountEvents(container) {
    var inputs = container.querySelectorAll(".amount-input");
    for (var i = 0; i < inputs.length; i++) {
      inputs[i].addEventListener("input", recalcTotals);
    }
  }

  function initAutocompleteInputs(container) {
    var inputs = container.querySelectorAll(".ac-input[data-autocomplete-type]");
    var bookId = getBookId();

    for (var i = 0; i < inputs.length; i++) {
      var input = inputs[i];
      var row = input.closest(".voucher-line-row") || document;
      var root = input.closest(".ac-root");
      if (!root) {
        continue;
      }

      (function (rowEl, inputEl, rootEl) {
        var targetNameSel = inputEl.getAttribute("data-target-name");
        var targetIdSel = inputEl.getAttribute("data-target-id");
        var acType = inputEl.getAttribute("data-autocomplete-type");

        new AutocompleteInput(rootEl, {
          type: acType,
          bookId: bookId,
          placeholder: inputEl.getAttribute("placeholder") || "",
          onSelect: function (item) {
            if (inputEl) {
              inputEl.value = item.code;
            }
            if (targetNameSel) {
              var nameInput = rowEl.querySelector(targetNameSel);
              if (nameInput) {
                nameInput.value = item.name;
              }
            }
            if (targetIdSel) {
              var idInput = rowEl.querySelector(targetIdSel);
              if (idInput) {
                idInput.value = item.id;
              }
            }
          },
          onChange: function (value) {
            if (!value) {
              if (targetNameSel) {
                var nameInput = rowEl.querySelector(targetNameSel);
                if (nameInput) {
                  nameInput.value = "";
                }
              }
              if (targetIdSel) {
                var idInput = rowEl.querySelector(targetIdSel);
                if (idInput) {
                  idInput.value = "";
                }
              }
            }
          },
        });
      })(row, input, root);
    }
  }

  function buildNewRow(index) {
    var row = document.createElement("tr");
    row.className = "voucher-line-row";
    row.setAttribute("data-row-index", String(index));

    row.innerHTML =
      '<td class="col-index">' +
      (index + 1) +
      '</td>' +
      '<td><input type="text" class="summary-input" name="lines[' +
      index +
      '][summary]"></td>' +
      '<td>' +
      '<div class="ac-root">' +
      '<input type="text" class="subject-code-input ac-input" name="lines[' +
      index +
      '][subject_code]" data-autocomplete-type="subject" data-target-name=".subject-name-input" data-target-id=".subject-id-input" placeholder="编码或名称">' +
      '<input type="hidden" class="subject-id-input" name="lines[' +
      index +
      '][subject_id]">' +
      '<div class="ac-dropdown"></div>' +
      '</div>' +
      '<input type="text" class="subject-name-input" name="lines[' +
      index +
      '][subject_name]" readonly>' +
      '</td>' +
      '<td><input type="text" class="aux-input" name="lines[' +
      index +
      '][aux_display]" placeholder="占位"></td>' +
      '<td><input type="number" class="amount-input debit-input" name="lines[' +
      index +
      '][debit]" min="0" step="0.01"></td>' +
      '<td><input type="number" class="amount-input credit-input" name="lines[' +
      index +
      '][credit]" min="0" step="0.01"></td>' +
      '<td><input type="date" class="due-input" name="lines[' +
      index +
      '][due_date]"></td>' +
      '<td><input type="text" class="note-input" name="lines[' +
      index +
      '][note]"></td>';

    return row;
  }

  function addLine() {
    var body = document.getElementById("voucher-lines-body");
    var index = body.querySelectorAll(".voucher-line-row").length;
    var row = buildNewRow(index);
    body.appendChild(row);
    initAutocompleteInputs(row);
    bindAmountEvents(row);
  }

  function collectLines() {
    var rows = document.querySelectorAll(".voucher-line-row");
    var lines = [];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var line = {
        summary: row.querySelector(".summary-input")?.value || "",
        subject_code: row.querySelector(".subject-code-input")?.value || "",
        subject_name: row.querySelector(".subject-name-input")?.value || "",
        subject_id: row.querySelector(".subject-id-input")?.value || "",
        aux_display: row.querySelector(".aux-input")?.value || "",
        debit: row.querySelector(".debit-input")?.value || "",
        credit: row.querySelector(".credit-input")?.value || "",
        due_date: row.querySelector(".due-input")?.value || "",
        note: row.querySelector(".note-input")?.value || "",
      };
      lines.push(line);
    }
    return lines;
  }

  function renderErrors(errors) {
    var box = document.getElementById("voucher-errors");
    if (!box) {
      return;
    }
    box.innerHTML = "";
    if (!errors || errors.length === 0) {
      box.classList.add("hidden");
      return;
    }
    box.classList.remove("hidden");
    var ul = document.createElement("ul");
    for (var i = 0; i < errors.length; i++) {
      var err = errors[i];
      var rowText = err.row ? "第" + err.row + "行" : "";
      var fieldText = err.field ? "（" + err.field + "）" : "";
      var message = err.message || err.error || "保存失败";
      var li = document.createElement("li");
      li.textContent = rowText + fieldText + "：" + message;
      ul.appendChild(li);
    }
    box.appendChild(ul);
  }

  function getOperatorHeaders() {
    var user = document.getElementById("operator-name")?.value || "";
    var role = document.getElementById("operator-role")?.value || "";
    return {
      "X-User": user,
      "X-Role": role,
    };
  }

  function saveVoucher() {
    var payload = {
      book_id: getBookId(),
      voucher_date: document.getElementById("voucher-date").value,
      voucher_word: document.getElementById("voucher-word").value,
      voucher_no: document.getElementById("voucher-no").value,
      attachments: document.getElementById("voucher-attachments").value,
      maker: document.getElementById("voucher-maker").value,
      status: "draft",
      lines: collectLines(),
    };

    fetch("/api/vouchers", {
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
          renderErrors(payload.data.errors || [{ message: payload.data.error }]);
          return;
        }
        renderErrors([]);
        document.getElementById("voucher-id").textContent = payload.data.voucher_id;
        document.getElementById("voucher-status").textContent = payload.data.status;
        alert("保存成功，凭证ID：" + payload.data.voucher_id);
      })
      .catch(function () {
        renderErrors([{ message: "请求失败" }]);
      });
  }

  function changeStatus(action) {
    var voucherId = document.getElementById("voucher-id").textContent;
    if (!voucherId || voucherId === "-") {
      renderErrors([{ message: "请先保存凭证" }]);
      return;
    }

    fetch("/api/vouchers/" + voucherId + "/" + action, {
      method: "POST",
      headers: getOperatorHeaders(),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          renderErrors([{ message: payload.data.error }]);
          return;
        }
        renderErrors([]);
        document.getElementById("voucher-status").textContent = payload.data.to_status;
        alert("操作成功：" + payload.data.action);
      })
      .catch(function () {
        renderErrors([{ message: "请求失败" }]);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var body = document.getElementById("voucher-lines-body");
    initAutocompleteInputs(body);
    bindAmountEvents(body);
    recalcTotals();

    var addBtn = document.getElementById("add-line-btn");
    if (addBtn) {
      addBtn.addEventListener("click", addLine);
    }

    var saveBtn = document.getElementById("save-voucher-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", saveVoucher);
    }

    var approveBtn = document.getElementById("approve-voucher-btn");
    if (approveBtn) {
      approveBtn.addEventListener("click", function () {
        changeStatus("approve");
      });
    }

    var unapproveBtn = document.getElementById("unapprove-voucher-btn");
    if (unapproveBtn) {
      unapproveBtn.addEventListener("click", function () {
        changeStatus("unapprove");
      });
    }

    var postBtn = document.getElementById("post-voucher-btn");
    if (postBtn) {
      postBtn.addEventListener("click", function () {
        changeStatus("post");
      });
    }

    var unpostBtn = document.getElementById("unpost-voucher-btn");
    if (unpostBtn) {
      unpostBtn.addEventListener("click", function () {
        changeStatus("unpost");
      });
    }
  });
})();
