(function () {
  var TZ_OFFSETS = {
    AoE: "-12:00",
    UTC: "+00:00",
    "UTC+0": "+00:00",
    "UTC-0": "+00:00",
    "UTC-12": "-12:00",
    "UTC-11": "-11:00",
    "UTC-10": "-10:00",
    "UTC-9": "-09:00",
    "UTC-8": "-08:00",
    "UTC-7": "-07:00",
    "UTC-6": "-06:00",
    "UTC-5": "-05:00",
    "UTC-4": "-04:00",
    "UTC-3": "-03:00",
    "UTC-2": "-02:00",
    "UTC-1": "-01:00",
    "UTC+1": "+01:00",
    "UTC+2": "+02:00",
    "UTC+3": "+03:00",
    "UTC+4": "+04:00",
    "UTC+5": "+05:00",
    "UTC+6": "+06:00",
    "UTC+7": "+07:00",
    "UTC+8": "+08:00",
    "UTC+9": "+09:00",
    "UTC+10": "+10:00",
    "UTC+11": "+11:00",
    "UTC+12": "+12:00",
  };

  var PAST_WINDOW_MS = 1000 * 60 * 60 * 24 * 90;
  var URGENT_MS = 1000 * 60 * 60 * 24 * 7;

  function parseNaiveInTimeZone(naive, timeZone) {
    var asUtc = new Date(naive + "Z");
    if (isNaN(asUtc.getTime())) {
      return null;
    }
    var formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    });
    var parts = formatter.formatToParts(asUtc);
    var map = {};
    parts.forEach(function (part) {
      if (part.type !== "literal") {
        map[part.type] = part.value;
      }
    });
    var asIfUtc = Date.UTC(
      Number(map.year),
      Number(map.month) - 1,
      Number(map.day),
      Number(map.hour),
      Number(map.minute),
      Number(map.second)
    );
    return new Date(asUtc.getTime() + (asUtc.getTime() - asIfUtc));
  }

  function parseDeadline(value, timezone) {
    if (!value || value === "TBD") {
      return null;
    }
    var naive = value.trim().replace(" ", "T");
    if (timezone === "PT") {
      return parseNaiveInTimeZone(naive, "America/Los_Angeles");
    }
    var offset = TZ_OFFSETS[timezone] || TZ_OFFSETS.AoE;
    var parsed = new Date(naive + offset);
    return isNaN(parsed.getTime()) ? null : parsed;
  }

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function formatCountdown(ms) {
    var past = ms < 0;
    var abs = Math.abs(ms);
    var days = Math.floor(abs / 86400000);
    var hours = Math.floor((abs % 86400000) / 3600000);
    var mins = Math.floor((abs % 3600000) / 60000);
    var secs = Math.floor((abs % 60000) / 1000);

    if (past) {
      if (days >= 60) {
        return Math.floor(days / 30) + " months ago";
      }
      if (days >= 1) {
        return days + (days === 1 ? " day ago" : " days ago");
      }
      if (hours >= 1) {
        return hours + (hours === 1 ? " hour ago" : " hours ago");
      }
      return mins + " min ago";
    }

    return days + " days " + pad(hours) + "h " + pad(mins) + "m " + pad(secs) + "s";
  }

  function rankLabel(edition) {
    var ifLabel =
      edition.bk21_if === null || edition.bk21_if === undefined || edition.bk21_if === ""
        ? "IF-"
        : "IF" + edition.bk21_if;
    var kiise = edition.kiise || "-";
    var core = edition.core || "-";
    return ifLabel + " / " + kiise + " / " + core;
  }

  function flatten(editions) {
    var rows = [];
    (editions || []).forEach(function (edition) {
      var cycles = edition.deadlines || [];
      cycles.forEach(function (item, index) {
        var parsed = parseDeadline(item.deadline, edition.timezone);
        rows.push({
          key: (edition.id || edition.title) + "-" + index,
          title: edition.title,
          year: edition.year,
          description: edition.description,
          tags: edition.tags || [],
          link: edition.link,
          date: edition.date,
          place: edition.place,
          timezone: edition.timezone,
          kiise: edition.kiise,
          bk21_if: edition.bk21_if,
          core: edition.core,
          comment: item.comment,
          abstractDeadline: item.abstract_deadline,
          deadline: item.deadline,
          parsed: parsed,
          cycleIndex: index,
          cycleCount: cycles.length,
        });
      });
    });
    return rows;
  }

  function byDeadline(a, b) {
    if (!a.parsed && !b.parsed) {
      return 0;
    }
    if (!a.parsed) {
      return 1;
    }
    if (!b.parsed) {
      return -1;
    }
    return a.parsed - b.parsed;
  }

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
        return '<span class="conf-tag conf-tag-' + escapeHtml(tag) + '">' + escapeHtml(tag) + "</span>";
      })
      .join("");
  }

  function cardHtml(row) {
    var title = escapeHtml(row.title) + " " + escapeHtml(row.year || "");
    var heading = row.link
      ? '<a href="' + escapeHtml(row.link) + '" target="_blank" rel="noopener">' + title + "</a>"
      : title;
    var where = [row.date, row.place].filter(Boolean).join(" / ");
    var cycle =
      row.cycleCount > 1
        ? "Deadline (" + (row.cycleIndex + 1) + " / " + row.cycleCount + ")"
        : "Deadline";
    if (row.comment) {
      cycle += " · " + row.comment;
    }
    var remainingClass = "conf-remaining";
    if (row.parsed) {
      var delta = row.parsed.getTime() - Date.now();
      if (delta < 0) {
        remainingClass += " is-past";
      } else if (delta < URGENT_MS) {
        remainingClass += " is-urgent";
      }
    }

    return (
      '<article class="conf-card" data-tags="' +
      escapeHtml(row.tags.join(",")) +
      '">' +
      '<div class="conf-card-main">' +
      '<div class="conf-card-title">' +
      "<h3>" +
      heading +
      "</h3>" +
      '<div class="conf-tags">' +
      tagBadges(row.tags) +
      "</div>" +
      '<span class="conf-ranks">(' +
      escapeHtml(rankLabel(row)) +
      ")</span>" +
      "</div>" +
      (where ? '<p class="conf-where">' + escapeHtml(where) + "</p>" : "") +
      '<p class="conf-deadline-meta">' +
      escapeHtml(cycle) +
      ": " +
      escapeHtml(row.deadline === "TBD" || !row.deadline ? "TBD" : row.deadline + " " + (row.timezone || "AoE")) +
      "</p>" +
      "</div>" +
      '<div class="' +
      remainingClass +
      '" data-deadline="' +
      (row.parsed ? row.parsed.toISOString() : "") +
      '">' +
      (row.parsed ? formatCountdown(row.parsed.getTime() - Date.now()) : "TBD") +
      "</div>" +
      "</article>"
    );
  }

  function matchesFilter(row, filter) {
    return filter === "ALL" || (row.tags || []).indexOf(filter) !== -1;
  }

  function render(state) {
    var now = Date.now();
    var upcoming = [];
    var past = [];

    state.rows.forEach(function (row) {
      if (!matchesFilter(row, state.filter)) {
        return;
      }
      if (!row.parsed) {
        upcoming.push(row);
        return;
      }
      var delta = row.parsed.getTime() - now;
      if (delta >= 0) {
        upcoming.push(row);
      } else if (-delta <= PAST_WINDOW_MS) {
        past.push(row);
      }
    });

    upcoming.sort(byDeadline);
    past.sort(function (a, b) {
      return byDeadline(b, a);
    });

    var upcomingEl = document.getElementById("conf-upcoming");
    var pastEl = document.getElementById("conf-past");
    upcomingEl.innerHTML = upcoming.length
      ? upcoming.map(cardHtml).join("")
      : '<p class="conf-empty">다가오는 데드라인이 없습니다.</p>';
    pastEl.innerHTML = past.length
      ? past.map(cardHtml).join("")
      : '<p class="conf-empty">최근 지난 데드라인이 없습니다.</p>';
  }

  function tick() {
    var nodes = document.querySelectorAll(".conf-remaining[data-deadline]");
    var now = Date.now();
    nodes.forEach(function (node) {
      var iso = node.getAttribute("data-deadline");
      if (!iso) {
        return;
      }
      var parsed = new Date(iso);
      var delta = parsed.getTime() - now;
      node.textContent = formatCountdown(delta);
      node.classList.toggle("is-past", delta < 0);
      node.classList.toggle("is-urgent", delta >= 0 && delta < URGENT_MS);
    });
  }

  function initFilters(tags, state) {
    var root = document.getElementById("conf-filters");
    var buttons = [{ id: "ALL", name: "All" }].concat(tags);
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

  var payloadEl = document.getElementById("conference-payload");
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
    rows: flatten(data.editions || []),
  };

  var updatedEl = document.getElementById("conf-updated");
  if (updatedEl) {
    updatedEl.textContent = formatUpdated(data.updated_at);
  }

  initFilters(catalog.tags || [], state);
  render(state);
  setInterval(tick, 1000);
})();
