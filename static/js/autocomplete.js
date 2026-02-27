(function () {
  function debounce(fn, delay) {
    var timer = null;
    return function () {
      var args = arguments;
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(function () {
        fn.apply(null, args);
      }, delay);
    };
  }

  function AutocompleteInput(root, options) {
    if (!root) {
      throw new Error("root element is required");
    }
    if (!options || !options.type) {
      throw new Error("type is required");
    }
    if (!options.bookId) {
      throw new Error("bookId is required");
    }
    this.root = root;
    this.input = root.querySelector(".ac-input");
    this.dropdown = root.querySelector(".ac-dropdown");

    this.type = options.type;
    this.bookId = options.bookId;
    this.placeholder = options.placeholder || "";
    this.limit = options.limit || 20;
    this.disabled = !!options.disabled;
    this.onSelect = options.onSelect || function () {};
    this.onChange = options.onChange || function () {};

    this.items = [];
    this.activeIndex = -1;

    this.input.placeholder = this.placeholder;
    this.input.disabled = this.disabled;

    this._bind();
  }

  AutocompleteInput.prototype._bind = function () {
    var self = this;

    var handleInput = debounce(function (value) {
      self._fetch(value);
      self.onChange(value);
    }, 200);

    this.input.addEventListener("input", function (e) {
      handleInput(e.target.value.trim());
    });

    this.input.addEventListener("keydown", function (e) {
      if (!self.dropdown.classList.contains("open")) {
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        self._move(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        self._move(-1);
      } else if (e.key === "Enter") {
        e.preventDefault();
        self._selectActive();
      } else if (e.key === "Escape") {
        e.preventDefault();
        self._close();
      }
    });

    document.addEventListener("click", function (e) {
      if (!self.root.contains(e.target)) {
        self._close();
      }
    });
  };

  AutocompleteInput.prototype._fetch = function (q) {
    var self = this;
    if (!q) {
      self._render([]);
      return;
    }

    var url =
      "/api/autocomplete?type=" +
      encodeURIComponent(self.type) +
      "&book_id=" +
      encodeURIComponent(self.bookId) +
      "&q=" +
      encodeURIComponent(q) +
      "&limit=" +
      encodeURIComponent(self.limit);

    fetch(url)
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (payload) {
        if (!payload.ok) {
          var msg = (payload.data && payload.data.error) || "请求失败";
          self._renderError(msg);
          return;
        }
        var items = payload.data.items || [];
        self._render(items);
      })
      .catch(function () {
        self._renderError("请求失败");
      });
  };

  AutocompleteInput.prototype._render = function (items) {
    var self = this;
    this.items = items;
    this.activeIndex = -1;
    this.dropdown.innerHTML = "";

    if (!items || items.length === 0) {
      this.dropdown.innerHTML = '<div class="ac-empty">无匹配结果</div>';
      this._open();
      return;
    }

    items.forEach(function (item, index) {
      var div = document.createElement("div");
      div.className = "ac-item";
      div.textContent = item.display_text;
      div.addEventListener("click", function () {
        self._select(index);
      });
      self.dropdown.appendChild(div);
    });

    this._open();
  };

  AutocompleteInput.prototype._renderError = function (message) {
    this.items = [];
    this.activeIndex = -1;
    this.dropdown.innerHTML =
      '<div class="ac-empty">' + (message || "请求失败") + "</div>";
    this._open();
  };

  AutocompleteInput.prototype._move = function (step) {
    if (!this.items.length) {
      return;
    }
    this.activeIndex += step;
    if (this.activeIndex < 0) {
      this.activeIndex = this.items.length - 1;
    }
    if (this.activeIndex >= this.items.length) {
      this.activeIndex = 0;
    }
    this._highlight();
  };

  AutocompleteInput.prototype._highlight = function () {
    var children = this.dropdown.querySelectorAll(".ac-item");
    for (var i = 0; i < children.length; i++) {
      if (i === this.activeIndex) {
        children[i].classList.add("active");
      } else {
        children[i].classList.remove("active");
      }
    }
  };

  AutocompleteInput.prototype._selectActive = function () {
    if (this.activeIndex < 0 || this.activeIndex >= this.items.length) {
      return;
    }
    this._select(this.activeIndex);
  };

  AutocompleteInput.prototype._select = function (index) {
    var item = this.items[index];
    if (!item) {
      return;
    }
    this.input.value = item.display_text;
    this.onSelect(item);
    this._close();
  };

  AutocompleteInput.prototype._open = function () {
    this.dropdown.classList.add("open");
  };

  AutocompleteInput.prototype._close = function () {
    this.dropdown.classList.remove("open");
    this.activeIndex = -1;
  };

  window.AutocompleteInput = AutocompleteInput;
})();
