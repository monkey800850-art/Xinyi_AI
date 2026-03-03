(function () {
  function byId(id) { return document.getElementById(id); }
  function val(id) { return (byId(id) && byId(id).value || "").trim(); }
  var msg = byId("payroll-msg");
  var result = byId("payroll-result");

  function setMsg(text) {
    if (msg) msg.textContent = "状态：" + text;
  }

  function render(data) {
    if (result) result.textContent = JSON.stringify(data, null, 2);
  }

  function getHeaders() {
    var headers = {
      "Content-Type": "application/json",
      "X-User": val("operator") || "uat_admin",
      "X-Role": val("role") || "payroll"
    };
    var operatorId = val("operator-id");
    var employeeId = val("employee-id");
    if (operatorId) headers["X-Operator-Id"] = operatorId;
    if (employeeId) headers["X-Employee-Id"] = employeeId;
    return headers;
  }

  function request(url, method, payload, label, raw) {
    setMsg(label + "中...");
    return fetch(url, {
      method: method || "GET",
      headers: getHeaders(),
      body: payload ? JSON.stringify(payload) : undefined
    }).then(function (resp) {
      if (raw) {
        if (!resp.ok) {
          return resp.text().then(function (t) {
            throw { status_code: resp.status, error: t || "request_failed" };
          });
        }
        return resp.blob().then(function (blob) {
          return { blob: blob, headers: resp.headers, status: resp.status };
        });
      }
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok) {
          data = data || {};
          data.status_code = resp.status;
          throw data;
        }
        return data;
      });
    }).then(function (data) {
      setMsg(label + "成功");
      render(data);
      return data;
    }).catch(function (err) {
      setMsg(label + "失败");
      render({ ok: false, status_code: err && err.status_code || 0, error: err && (err.error || err.message || String(err)) || "unknown_error", detail: err });
      throw err;
    });
  }

  function monthToPeriod(monthValue) {
    return monthValue || val("period");
  }

  function periodToVoucherDate(period) {
    if (!/^\d{4}-\d{2}$/.test(period)) return "";
    var parts = period.split("-");
    var y = Number(parts[0]);
    var m = Number(parts[1]);
    var lastDay = new Date(y, m, 0).getDate();
    var dd = String(lastDay).padStart(2, "0");
    return period + "-" + dd;
  }

  function payloadPeriod() {
    return {
      book_id: Number(val("book-id")),
      period: monthToPeriod(val("period")),
      status: val("period-status") || "open"
    };
  }

  function payloadSlip() {
    return {
      id: val("slip-id") ? Number(val("slip-id")) : undefined,
      book_id: Number(val("book-id")),
      period: monthToPeriod(val("period")),
      employee_id: Number(val("employee-id")),
      employee_name: val("employee-name"),
      department: val("department"),
      city: val("city"),
      bank_account: val("bank-account"),
      attendance_ref: val("attendance-ref"),
      attendance_days: Number(val("attendance-days") || 0),
      absent_days: Number(val("absent-days") || 0),
      gross_amount: Number(val("gross-amount") || 0),
      deduction_amount: Number(val("deduction-amount") || 0),
      social_insurance: Number(val("social-insurance") || 0),
      housing_fund: Number(val("housing-fund") || 0),
      bonus_amount: Number(val("bonus-amount") || 0),
      overtime_amount: Number(val("overtime-amount") || 0),
      tax_method: val("tax-method") || "cumulative"
    };
  }

  function selectedSlipId() {
    var sid = val("slip-id");
    if (!sid) throw new Error("请先填写工资单ID");
    return Number(sid);
  }

  function selectedBatchId() {
    var bid = val("batch-id");
    if (!bid) throw new Error("请先填写批次ID");
    return Number(bid);
  }

  function getSlipQueryUrl() {
    var qs = "book_id=" + encodeURIComponent(val("book-id"));
    var period = monthToPeriod(val("period"));
    if (period) qs += "&period=" + encodeURIComponent(period);
    return "/api/payroll/slips?" + qs;
  }

  function getPeriodQueryUrl() {
    return "/api/payroll/periods?book_id=" + encodeURIComponent(val("book-id"));
  }

  function getBatchQueryUrl() {
    var qs = "book_id=" + encodeURIComponent(val("book-id"));
    var period = monthToPeriod(val("period"));
    if (period) qs += "&period=" + encodeURIComponent(period);
    return "/api/payroll/disbursement-batches?" + qs;
  }

  function downloadBlob(blob, fileName) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = fileName || "download.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function parseSlipIds() {
    var raw = val("batch-slip-ids");
    if (!raw) return [];
    return raw.split(",").map(function (x) { return Number(x.trim()); }).filter(function (n) { return Number.isFinite(n) && n > 0; });
  }

  byId("btn-period-upsert").addEventListener("click", function () {
    request("/api/payroll/periods", "POST", payloadPeriod(), "保存工资期间");
  });

  byId("btn-period-list").addEventListener("click", function () {
    request(getPeriodQueryUrl(), "GET", null, "查询工资期间");
  });

  byId("btn-period-close").addEventListener("click", function () {
    var pid = val("period-id");
    if (!pid) { setMsg("失败：请先填写期间ID"); return; }
    request("/api/payroll/periods/" + Number(pid) + "/close", "POST", {}, "封账");
  });

  byId("btn-period-reopen").addEventListener("click", function () {
    var pid = val("period-id");
    if (!pid) { setMsg("失败：请先填写期间ID"); return; }
    request("/api/payroll/periods/" + Number(pid) + "/reopen", "POST", {}, "反封账");
  });

  byId("btn-slip-upsert").addEventListener("click", function () {
    request("/api/payroll/slips", "POST", payloadSlip(), "编制工资单");
  });

  byId("btn-slip-list").addEventListener("click", function () {
    request(getSlipQueryUrl(), "GET", null, "查询工资单");
  });

  byId("btn-slip-confirm").addEventListener("click", function () {
    try {
      request("/api/payroll/slips/" + selectedSlipId() + "/confirm", "POST", {}, "计税确认");
    } catch (e) {
      setMsg("失败：" + e.message);
    }
  });

  byId("btn-voucher-suggest").addEventListener("click", function () {
    try {
      request("/api/payroll/slips/" + selectedSlipId() + "/voucher-suggestion", "GET", null, "查询凭证建议");
    } catch (e) {
      setMsg("失败：" + e.message);
    }
  });

  byId("btn-voucher-create").addEventListener("click", function () {
    var sid;
    try {
      sid = selectedSlipId();
    } catch (e) {
      setMsg("失败：" + e.message);
      return;
    }
    request("/api/payroll/slips/" + sid + "/voucher-suggestion", "GET", null, "加载凭证建议")
      .then(function (suggest) {
        var draft = suggest && suggest.voucher_draft || {};
        var period = suggest && suggest.period || monthToPeriod(val("period"));
        var payload = {
          book_id: Number(suggest.book_id || val("book-id")),
          voucher_date: periodToVoucherDate(period),
          voucher_word: draft.voucher_word || "记",
          voucher_no: val("voucher-no") || "",
          attachments: 0,
          maker: val("operator") || "payroll",
          status: "draft",
          lines: draft.lines || []
        };
        return request("/api/vouchers", "POST", payload, "自动生成工资凭证");
      });
  });

  byId("btn-payment-create").addEventListener("click", function () {
    try {
      request("/api/payroll/slips/" + selectedSlipId() + "/create-payment-request", "POST", {}, "创建发放申请");
    } catch (e) {
      setMsg("失败：" + e.message);
    }
  });

  byId("btn-payment-status").addEventListener("click", function () {
    try {
      request("/api/payroll/slips/" + selectedSlipId() + "/payment-status", "GET", null, "查询发放状态");
    } catch (e) {
      setMsg("失败：" + e.message);
    }
  });

  byId("btn-batch-create").addEventListener("click", function () {
    var payload = {
      book_id: Number(val("book-id")),
      period: monthToPeriod(val("period")),
      slip_ids: parseSlipIds()
    };
    request("/api/payroll/disbursement-batches", "POST", payload, "生成发放批次");
  });

  byId("btn-batch-list").addEventListener("click", function () {
    request(getBatchQueryUrl(), "GET", null, "查询发放批次");
  });

  byId("btn-bank-export").addEventListener("click", function () {
    var batchId;
    try {
      batchId = selectedBatchId();
    } catch (e) {
      setMsg("失败：" + e.message);
      return;
    }
    request("/api/payroll/disbursement-batches/" + batchId + "/bank-file", "GET", null, "导出银行文件", true)
      .then(function (res) {
        var cd = res.headers.get("content-disposition") || "";
        var match = /filename=\"?([^\";]+)\"?/i.exec(cd);
        downloadBlob(res.blob, match && match[1] ? match[1] : ("payroll_batch_" + batchId + ".csv"));
        render({ ok: true, batch_id: batchId, downloaded: true });
      })
      .catch(function () {});
  });
})();
