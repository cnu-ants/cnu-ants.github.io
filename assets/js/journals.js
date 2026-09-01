(function () {
  var CCF_ORDER = { A: 0, B: 1, C: 2 };

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function tagBadges(tags) {
    return tags
      .map(function (tag) {
        return (
          '<span class="conf-tag conf-tag-' +
          escapeHtml(tag) +
          '">' +
          escapeHtml(tag) +
          "</span>"
        );
      })
      .join("");
  }

  function ccfLabel(ccf) {
    return ccf ? "CCF " + ccf : "CCF -";
  }

  function metricBits(row) {
    var bits = [];
    if (row.publisher) {
      bits.push(row.publisher);
    }
    bits.push("Continuous submission");
    if (row.issn) {
      bits.push("ISSN " + row.issn);
    }
    return bits.join(" · ");
  }

  function statsBits(row) {
    var bits = [];
    if (row.citedness !== null && row.citedness !== undefined) {
      bits.push("OpenAlex citedness " + row.citedness);
    }
    if (row.h_index) {
      bits.push("h-index " + row.h_index);
    }
    if (row.is_oa) {
      bits.push("OA");
    } else if (row.apc_usd) {
      bits.push("APC $" + row.apc_usd);
    }
    return bits.join(" · ");
  }

  function linkBits(row) {
    var links = [];
    if (row.homepage) {
      links.push(
        '<a href="' +
          escapeHtml(row.homepage) +
          '" target="_blank" rel="noopener">Homepage</a>'
      );
    }
    if (row.openalex) {
      links.push(
        '<a href="' +
          escapeHtml(row.openalex) +
          '" target="_blank" rel="noopener">OpenAlex</a>'
      );
    }
    return links.join(" · ");
  }

  function cardHtml(row) {
    var title = escapeHtml(row.title);
    var heading = row.homepage
      ? '<a href="' +
        escapeHtml(row.homepage) +
        '" target="_blank" rel="noopener">' +
        title +
        "</a>"
      : title;
    var ccfClass = "journal-ccf" + (row.ccf ? " is-" + row.ccf : " is-none");

    return (
      '<article class="conf-card" data-tags="' +
      escapeHtml((row.tags || []).join(",")) +
      '">' +
      '<div class="conf-card-main">' +
      '<div class="conf-card-title">' +
      "<h3>" +
      heading +
      "</h3>" +
      '<div class="conf-tags">' +
      tagBadges(row.tags || []) +
      "</div>" +
      '<span class="conf-ranks">(' +
      escapeHtml(ccfLabel(row.ccf)) +
      ")</span>" +
      "</div>" +
      (row.name
        ? '<p class="conf-where">' + escapeHtml(row.name) + "</p>"
        : "") +
      '<p class="conf-deadline-meta">' +
      escapeHtml(metricBits(row)) +
      "</p>" +
      (statsBits(row)
        ? '<p class="conf-deadline-meta">' + escapeHtml(statsBits(row)) + "</p>"
        : "") +
      (linkBits(row)
        ? '<p class="conf-deadline-meta journal-links">' + linkBits(row) + "</p>"
        : "") +
      "</div>" +
      '<div class="' +
      ccfClass +
      '">' +
      escapeHtml(ccfLabel(row.ccf)) +
      "</div>" +
      "</article>"
    );
  }

  function matchesFilter(row, filter) {
    return filter === "ALL" || (row.tags || []).indexOf(filter) !== -1;
  }

  function byRankThenTitle(a, b) {
    var ra = CCF_ORDER.hasOwnProperty(a.ccf) ? CCF_ORDER[a.ccf] : 9;
    var rb = CCF_ORDER.hasOwnProperty(b.ccf) ? CCF_ORDER[b.ccf] : 9;
    if (ra !== rb) {
      return ra - rb;
    }
    return String(a.title).localeCompare(String(b.title));
  }

  function render(state) {
    var rows = state.rows.filter(function (row) {
      return matchesFilter(row, state.filter);
    });
    rows.sort(byRankThenTitle);
    var root = document.getElementById("journal-list");
    root.innerHTML = rows.length
      ? rows.map(cardHtml).join("")
      : '<p class="conf-empty">해당하는 저널이 없습니다.</p>';
  }

  function initFilters(tags, state) {
    var root = document.getElementById("journal-filters");
    var buttons = [{ id: "ALL" }].concat(tags);
    root.innerHTML = buttons
      .map(function (tag) {
        var id = tag.id;
        var label = id === "ALL" ? "All" : id;
        var active = state.filter === id ? " is-active" : "";
        return (
          '<button type="button" class="conf-filter' +
          active +
          '" data-filter="' +
          escapeHtml(id) +
          '">' +
          escapeHtml(label) +
          "</button>"
        );
      })
      .join("");

    root.addEventListener("click", function (event) {
      var button = event.target.closest("[data-filter]");
      if (!button) {
        return;
      }
      state.filter = button.getAttribute("data-filter");
      Array.prototype.forEach.call(root.querySelectorAll(".conf-filter"), function (el) {
        el.classList.toggle("is-active", el.getAttribute("data-filter") === state.filter);
      });
      render(state);
    });
  }

  function formatUpdated(value) {
    if (!value) {
      return "unknown";
    }
    var date = new Date(value);
    if (isNaN(date.getTime())) {
      return value;
    }
    return date.toISOString().slice(0, 10);
  }

  var payloadEl = document.getElementById("journal-payload");
  if (!payloadEl) {
    return;
  }

  var payload;
  try {
    payload = JSON.parse(payloadEl.textContent);
  } catch (error) {
    return;
  }

  var catalog = payload.catalog || {};
  var data = payload.data || {};
  var state = {
    filter: "ALL",
    rows: data.journals || [],
  };

  var updatedEl = document.getElementById("journal-updated");
  if (updatedEl) {
    updatedEl.textContent = formatUpdated(data.updated_at);
  }

  initFilters(catalog.tags || [], state);
  render(state);
})();
