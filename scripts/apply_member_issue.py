#!/usr/bin/env python3
"""Apply a member-profile GitHub issue to that member's existing page.

Identity is the issue author's GitHub login matched against `github:` in
`_members/*.md`. The issue may not create files, change `github`, or edit
anyone else's page.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required. Install with: pip install pyyaml\n")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
MEMBERS_DIR = ROOT / "_members"

IMMUTABLE_KEYS = {
    "github",
    "layout",
    "permalink",
    "visible",
    "pub_visible",
    "image",
    "name",
    "name_kor",
    "startdate",
    "office",
    "phone",
    "job",
    "gradyear",
    "academic-services",
    "affiliation",
}

PREFERRED_ORDER = [
    "visible",
    "pub_visible",
    "layout",
    "name",
    "name_kor",
    "email",
    "position",
    "gradyear",
    "affiliation",
    "position-display",
    "image",
    "permalink",
    "startdate",
    "office",
    "phone",
    "job",
    "github",
    "linkedin",
    "homepage",
    "scholar",
    "interests",
    "edu",
    "exps",
    "awards",
    "academic-services",
    "introduction",
]

CHECKBOX_TO_FIELD = {
    "이메일": "email",
    "직함 / 소속 상태": "position",
    "GitHub": "github",
    "LinkedIn": "linkedin",
    "관심 분야 (Research interests)": "interests",
    "짧은 소개": "introduction",
    "학력 (Education)": "edu",
    "경력 / 인턴": "exps",
    "수상 (Honors)": "awards",
    "개인 홈페이지": "homepage",
    "Google Scholar": "scholar",
    "프로필 사진": "photo",
    "기타": "notes",
}

VALUE_HEADINGS = {
    "email": "이메일",
    "position": "직함",
    "github": "GitHub",
    "linkedin": "LinkedIn",
    "interests": "관심 분야",
    "introduction": "짧은 소개",
    "edu": "학력",
    "exps": "경력 / 인턴",
    "awards": "수상",
    "homepage": "개인 홈페이지",
    "scholar": "Google Scholar",
}

POSITION_MAP = {
    "B.S. Student": ("Undergraduate", "B.S. Student"),
    "Intern": ("Undergraduate", "Intern"),
    "M.S. Student": ("Graduate", "M.S. Student"),
    "Integrated MS & Ph.D. student": ("Graduate", "Integrated MS & Ph.D. student"),
    "Ph.D. Student": ("Graduate", "Ph.D. Student"),
    "M.S. Student (part)": ("Graduate", "M.S. Student (part)"),
    "Ph.D. Student (part)": ("Graduate", "Ph.D. Student (part)"),
    "Alumni (M.S.)": ("Graduate", "M.S."),
    "Alumni (Ph.D.)": ("Graduate", "Ph.D."),
}

SKIP_POSITIONS = {"변경 없음", "기타 (아래 메모에 적어 주세요)"}

LIQUID_RE = re.compile(r"(\{\{|\{%|}}|%})")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GITHUB_USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")

MAX_TEXT = 2000
MAX_ITEMS = 20
MAX_ITEM = 240
MAX_URL = 300


class Rejected(Exception):
    """Expected rejection: comment on the issue, do not fail the workflow."""


def is_blank(value: str | None) -> bool:
    if value is None:
        return True
    text = value.strip()
    return text == "" or text == "_No response_"


def parse_issue_body(body: str | None) -> dict[str, str]:
    if not body:
        return {}
    normalized = body.replace("\r\n", "\n")
    parts = re.split(r"^### ", normalized, flags=re.M)
    fields: dict[str, str] = {}
    for part in parts[1:]:
        lines = part.split("\n")
        title = lines[0].strip()
        fields[title] = "\n".join(lines[1:]).strip()
    return fields


def checked_labels(section: str | None) -> set[str]:
    if not section:
        return set()
    checked: set[str] = set()
    for raw in section.splitlines():
        match = re.match(r"^[-*] \[[xX]\] (.+)$", raw.strip())
        if match:
            checked.add(match.group(1).strip())
    return checked


def strip_simple_html(text: str) -> str:
    text = re.sub(r'<a\s[^>]*href="([^"]+)"[^>]*>[^<]*</a>', r"\1", text, flags=re.I)
    return re.sub(r"<[^>]+>", "", text).strip()


def detect_mode(title: str, fields: dict[str, str]) -> str:
    if title.startswith("[Member] Add info:"):
        return "add"
    if title.startswith("[Member] Update info:"):
        return "update"
    if "추가할 항목" in fields:
        return "add"
    if "수정할 항목" in fields:
        return "update"
    raise Rejected("멤버 정보 추가/수정 템플릿으로 열린 이슈가 아닙니다.")


def normalize_github(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lstrip("@")
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("github.com/"):
        parsed = urlparse(text if "://" in text else f"https://{text}")
        host = (parsed.netloc or "").lower()
        if host not in {"github.com", "www.github.com"}:
            return None
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) != 1:
            return None
        text = parts[0]
    if "/" in text or " " in text:
        return None
    if not GITHUB_USER_RE.match(text):
        return None
    return text.lower()


def member_slug(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip().rstrip("/")
    match = re.search(r"/members/([^/?#]+)", text)
    if match:
        return match.group(1).lower()
    if "/" not in text:
        return text.lower()
    return text.rsplit("/", 1)[-1].lower()


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        raise Rejected("멤버 파일 front matter를 읽지 못했습니다.")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise Rejected("멤버 파일 front matter를 읽지 못했습니다.")
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise Rejected("멤버 파일 YAML이 객체가 아닙니다.")
    return data, parts[2]


def needs_quotes(text: str) -> bool:
    if text == "" or text.strip() != text:
        return True
    if text.lower() in {"true", "false", "null", "yes", "no", "on", "off"}:
        return True
    if text[0] in "-?:@`&*!|>%'\"{}[]":
        return True
    if any(ch in text for ch in ":#{}[],&*?|>%'\"@"):
        return True
    return False


def dump_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    if "\n" in text:
        raise ValueError("multiline scalar needs block handling")
    if needs_quotes(text):
        return json.dumps(text, ensure_ascii=False)
    return text


def dump_key(key: str, value: Any) -> list[str]:
    if value is None:
        return [f"{key}:"]
    if isinstance(value, bool) or (isinstance(value, int) and not isinstance(value, bool)):
        return [f"{key}: {dump_scalar(value)}"]
    if isinstance(value, str):
        if "\n" in value:
            lines = [f"{key}: |"]
            for line in value.split("\n"):
                lines.append(f"  {line}")
            return lines
        return [f"{key}: {dump_scalar(value)}"]
    if isinstance(value, list):
        if not value:
            return [f"{key}: []"]
        if all(isinstance(item, str) for item in value):
            lines = [f"{key}:"]
            for item in value:
                lines.append(f"  - {dump_scalar(item)}")
            return lines
        if all(isinstance(item, list) for item in value):
            lines = [f"{key}:"]
            for item in value:
                inner = ", ".join(dump_scalar(part) for part in item)
                lines.append(f"  - [{inner}]")
            return lines
    dumped = yaml.safe_dump({key: value}, allow_unicode=True, sort_keys=False).rstrip()
    return dumped.split("\n")


def ordered_keys(data: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in data:
        if key not in keys:
            keys.append(key)
    preferred = [key for key in PREFERRED_ORDER if key in data]
    rest = [key for key in keys if key not in preferred]
    preferred_set = set(preferred)
    out: list[str] = []
    original_without_preferred = [key for key in keys if key not in preferred_set]
    # Keep original relative order, but pin known keys into PREFERRED_ORDER.
    seen: set[str] = set()
    for key in PREFERRED_ORDER:
        if key in data and key not in seen:
            out.append(key)
            seen.add(key)
    for key in original_without_preferred:
        if key not in seen:
            out.append(key)
            seen.add(key)
    for key in rest:
        if key not in seen:
            out.append(key)
    return out


def dump_front_matter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key in ordered_keys(data):
        lines.extend(dump_key(key, data[key]))
    lines.append("---")
    return "\n".join(lines) + "\n"


def replace_or_insert_key(front_matter: str, key: str, block: str) -> str:
    pattern = re.compile(
        rf"(?ms)^{re.escape(key)}:.*?(?=^[A-Za-z0-9_-]+:|\Z)",
    )
    replacement = block.rstrip() + "\n"
    if pattern.search(front_matter):
        return pattern.sub(replacement, front_matter, count=1)
    if not front_matter.endswith("\n"):
        front_matter += "\n"
    return front_matter + replacement


def patch_member_file(original: str, data: dict[str, Any], keys: list[str]) -> str:
    if not original.startswith("---"):
        raise Rejected("멤버 파일 front matter를 읽지 못했습니다.")
    parts = original.split("---", 2)
    if len(parts) < 3:
        raise Rejected("멤버 파일 front matter를 읽지 못했습니다.")
    front_matter = parts[1]
    rest = parts[2]
    for key in keys:
        if key not in data:
            continue
        block = "\n".join(dump_key(key, data[key]))
        front_matter = replace_or_insert_key(front_matter, key, block)
    patched = "---" + front_matter + "---" + rest
    parsed, _body = split_front_matter(patched)
    for key in keys:
        if parsed.get(key) != data.get(key):
            raise Rejected(f"{key} 값을 파일에 안전하게 쓰지 못했습니다.")
    return patched


def load_members(members_dir: Path) -> list[tuple[Path, dict[str, Any], str]]:
    members: list[tuple[Path, dict[str, Any], str]] = []
    for path in sorted(members_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        data, body = split_front_matter(text)
        members.append((path, data, body))
    return members


def find_member_by_github(
    members: list[tuple[Path, dict[str, Any], str]], login: str
) -> tuple[Path, dict[str, Any], str]:
    login_norm = normalize_github(login)
    if not login_norm:
        raise Rejected("이슈 작성자의 GitHub 아이디를 확인하지 못했습니다.")
    matches = []
    for path, data, body in members:
        member_github = normalize_github(data.get("github"))
        if member_github and member_github == login_norm:
            matches.append((path, data, body))
    if not matches:
        raise Rejected(
            "이슈 작성자의 GitHub 아이디가 멤버 파일에 연결되어 있지 않습니다. "
            "관리자가 `_members` 파일에 `github: 아이디`를 넣은 뒤에 다시 열어 주세요."
        )
    if len(matches) > 1:
        raise Rejected("같은 GitHub 아이디가 여러 멤버 파일에 있습니다. 관리자가 확인해야 합니다.")
    return matches[0]


def assert_same_person(fields: dict[str, str], data: dict[str, Any], path: Path) -> None:
    name = strip_simple_html(fields.get("이름 (English)", ""))
    name_kor = strip_simple_html(fields.get("이름 (한글)", ""))
    url = strip_simple_html(fields.get("멤버 페이지 주소", ""))
    if is_blank(name) or is_blank(name_kor):
        raise Rejected("이름(English/한글)이 비어 있습니다.")
    if name.lower() != str(data.get("name", "")).strip().lower():
        raise Rejected("영어 이름이 연결된 프로필과 다릅니다. 본인 페이지만 수정할 수 있습니다.")
    if name_kor != str(data.get("name_kor", "")).strip():
        raise Rejected("한글 이름이 연결된 프로필과 다릅니다. 본인 페이지만 수정할 수 있습니다.")
    if not is_blank(url):
        claimed = member_slug(url)
        actual = member_slug(str(data.get("permalink") or path.stem))
        if not claimed or claimed != actual:
            raise Rejected("멤버 페이지 주소가 본인 프로필이 아닙니다.")


def assert_safe_text(text: str, label: str) -> None:
    if len(text) > MAX_TEXT:
        raise Rejected(f"{label}이(가) 너무 깁니다.")
    if LIQUID_RE.search(text) or "---" in text:
        raise Rejected(f"{label}에 사용할 수 없는 문자가 있습니다.")


def https_url(value: str, label: str, allowed_hosts: set[str] | None = None) -> str:
    text = strip_simple_html(value)
    if len(text) > MAX_URL:
        raise Rejected(f"{label} 주소가 너무 깁니다.")
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise Rejected(f"{label}는 https 주소만 넣을 수 있습니다.")
    host = parsed.netloc.lower()
    if allowed_hosts and host not in allowed_hosts and not any(host.endswith("." + h) for h in allowed_hosts):
        raise Rejected(f"{label} 주소가 허용된 사이트가 아닙니다.")
    return text


def parse_csv_lines(text: str, min_parts: int, max_parts: int, label: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = strip_simple_html(raw).strip()
        if not line:
            continue
        assert_safe_text(line, label)
        if len(line) > MAX_ITEM * max_parts:
            raise Rejected(f"{label} 한 줄이 너무 깁니다.")
        parts = [part.strip() for part in line.split(",")]
        parts = [part for part in parts if part]
        if len(parts) < min_parts:
            raise Rejected(f"{label}은(는) 쉼표로 구분해 주세요. 예시는 이슈 템플릿을 참고하면 됩니다.")
        if len(parts) > max_parts:
            head = parts[: max_parts - 1]
            tail = ", ".join(parts[max_parts - 1 :])
            parts = head + [tail]
        rows.append(parts)
    if not rows:
        raise Rejected(f"{label} 내용이 비어 있습니다.")
    if len(rows) > MAX_ITEMS:
        raise Rejected(f"{label} 항목이 너무 많습니다.")
    return rows


def parse_interests(text: str) -> list[str]:
    assert_safe_text(text, "관심 분야")
    items = [strip_simple_html(part).strip() for part in text.replace("\n", ",").split(",")]
    items = [item for item in items if item]
    if not items:
        raise Rejected("관심 분야 내용이 비어 있습니다.")
    if len(items) > MAX_ITEMS:
        raise Rejected("관심 분야가 너무 많습니다.")
    for item in items:
        if len(item) > 80:
            raise Rejected("관심 분야 항목이 너무 깁니다.")
    return items


def existing(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    if value is None or value == "" or value == []:
        return False
    return True


def apply_fields(
    data: dict[str, Any],
    mode: str,
    fields: dict[str, str],
    checked: set[str],
    author: str,
) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    updated = dict(data)
    applied: list[str] = []
    skipped: list[str] = []
    changed_keys: list[str] = []

    def maybe_set(field: str, label: str, value: Any) -> None:
        if field in IMMUTABLE_KEYS:
            skipped.append(f"{label}: 자동으로 바꾸지 않습니다.")
            return
        if mode == "add" and existing(updated, field):
            skipped.append(f"{label}: 이미 값이 있어 추가 템플릿으로는 덮어쓰지 않았습니다.")
            return
        updated[field] = value
        applied.append(label)
        if field not in changed_keys:
            changed_keys.append(field)

    wanted = {CHECKBOX_TO_FIELD[label] for label in checked if label in CHECKBOX_TO_FIELD}
    if not wanted:
        raise Rejected("선택한 항목이 없습니다. 체크박스에서 넣을 정보를 골라 주세요.")

    for field, heading in VALUE_HEADINGS.items():
        if field in wanted:
            continue
        if not is_blank(fields.get(heading)):
            skipped.append(f"{heading}: 값이 있지만 체크하지 않아 반영하지 않았습니다.")

    if "github" in wanted:
        github_value = fields.get("GitHub", "")
        if not is_blank(github_value):
            submitted = normalize_github(strip_simple_html(github_value))
            if submitted != normalize_github(author):
                raise Rejected("이슈의 GitHub 칸이 이슈 작성자 아이디와 다릅니다.")
        skipped.append("GitHub 아이디는 관리자가 멤버 파일에 연결하며, 이슈로는 바꾸지 않습니다.")

    if "photo" in wanted:
        skipped.append("프로필 사진은 자동 반영하지 않습니다. 관리자가 이슈 첨부를 보고 넣습니다.")

    if "notes" in wanted:
        skipped.append("기타 요청은 자동 반영하지 않습니다. 관리자가 메모를 보고 처리합니다.")

    if "email" in wanted:
        if mode != "update":
            skipped.append("이메일은 수정 템플릿에서만 바꿀 수 있습니다.")
        elif is_blank(fields.get("이메일")):
            skipped.append("이메일을 선택했지만 값이 비어 있습니다.")
        else:
            email = strip_simple_html(fields["이메일"])
            if not EMAIL_RE.match(email) or len(email) > 120:
                raise Rejected("이메일 형식이 올바르지 않습니다.")
            maybe_set("email", "이메일", email)

    if "position" in wanted:
        if mode != "update":
            skipped.append("직함은 수정 템플릿에서만 바꿀 수 있습니다.")
        else:
            position = strip_simple_html(fields.get("직함", ""))
            if is_blank(position) or position in SKIP_POSITIONS:
                skipped.append("직함을 선택했지만 변경 값이 없습니다.")
            elif position not in POSITION_MAP:
                skipped.append("직함 기타는 자동 반영하지 않습니다. 관리자가 메모를 보고 처리합니다.")
            else:
                pos, display = POSITION_MAP[position]
                if mode == "add" and existing(updated, "position-display"):
                    skipped.append("직함: 이미 값이 있어 추가 템플릿으로는 덮어쓰지 않았습니다.")
                else:
                    updated["position"] = pos
                    updated["position-display"] = display
                    applied.append("직함")
                    for key in ("position", "position-display"):
                        if key not in changed_keys:
                            changed_keys.append(key)

    if "linkedin" in wanted:
        if is_blank(fields.get("LinkedIn")):
            skipped.append("LinkedIn을 선택했지만 값이 비어 있습니다.")
        else:
            url = https_url(
                fields["LinkedIn"],
                "LinkedIn",
                {"linkedin.com", "www.linkedin.com"},
            )
            maybe_set("linkedin", "LinkedIn", url)

    if "homepage" in wanted:
        if is_blank(fields.get("개인 홈페이지")):
            skipped.append("개인 홈페이지를 선택했지만 값이 비어 있습니다.")
        else:
            url = https_url(fields["개인 홈페이지"], "개인 홈페이지")
            maybe_set("homepage", "개인 홈페이지", url)

    if "scholar" in wanted:
        if is_blank(fields.get("Google Scholar")):
            skipped.append("Google Scholar를 선택했지만 값이 비어 있습니다.")
        else:
            url = https_url(
                fields["Google Scholar"],
                "Google Scholar",
                {"scholar.google.com", "scholar.google.co.kr"},
            )
            maybe_set("scholar", "Google Scholar", url)

    if "interests" in wanted:
        if is_blank(fields.get("관심 분야")):
            skipped.append("관심 분야를 선택했지만 값이 비어 있습니다.")
        else:
            maybe_set("interests", "관심 분야", parse_interests(fields["관심 분야"]))

    if "introduction" in wanted:
        if is_blank(fields.get("짧은 소개")):
            skipped.append("짧은 소개를 선택했지만 값이 비어 있습니다.")
        else:
            intro = strip_simple_html(fields["짧은 소개"]).strip()
            assert_safe_text(intro, "짧은 소개")
            maybe_set("introduction", "짧은 소개", intro)

    if "edu" in wanted:
        if is_blank(fields.get("학력")):
            skipped.append("학력을 선택했지만 값이 비어 있습니다.")
        else:
            maybe_set("edu", "학력", parse_csv_lines(fields["학력"], 3, 4, "학력"))

    if "exps" in wanted:
        if is_blank(fields.get("경력 / 인턴")):
            skipped.append("경력을 선택했지만 값이 비어 있습니다.")
        else:
            maybe_set("exps", "경력 / 인턴", parse_csv_lines(fields["경력 / 인턴"], 3, 4, "경력 / 인턴"))

    if "awards" in wanted:
        if is_blank(fields.get("수상")):
            skipped.append("수상을 선택했지만 값이 비어 있습니다.")
        else:
            maybe_set("awards", "수상", parse_csv_lines(fields["수상"], 3, 3, "수상"))

    if not applied:
        raise Rejected("자동으로 반영할 값이 없습니다.\n\n" + format_notes(skipped))
    return updated, applied, skipped, changed_keys


def format_notes(items: list[str]) -> str:
    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items)


def roundtrip_ok(data: dict[str, Any]) -> None:
    dumped = dump_front_matter(data)
    parsed, _body = split_front_matter(dumped + "\n")
    if parsed.get("github") != data.get("github"):
        raise Rejected("YAML 검증 중 github 필드가 달라졌습니다.")
    if parsed.get("permalink") != data.get("permalink"):
        raise Rejected("YAML 검증 중 permalink가 달라졌습니다.")
    yaml.safe_load(dumped.split("---", 2)[1])


def build_comment(ok: bool, path: Path | None, applied: list[str], skipped: list[str], message: str) -> str:
    if not ok:
        return "자동 반영을 건너뛰었습니다.\n\n" + message
    lines = [
        f"Jekyll 빌드가 성공해 `{path.name}` 변경을 `main`에 푸시했습니다.",
        "",
        format_notes([f"반영: {item}" for item in applied]),
    ]
    if skipped:
        lines.extend(["", "아래는 자동으로 넣지 않았습니다.", format_notes(skipped)])
    return "\n".join(lines).strip() + "\n"


def post_issue_comment(body: str) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    number = os.environ.get("ISSUE_NUMBER")
    if not token or not repo or not number:
        sys.stderr.write("No GitHub issue context; comment was not posted.\n")
        sys.stderr.write(body + "\n")
        return
    payload = json.dumps({"body": body}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "cnu-ants-member-issue",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.URLError as error:
        sys.stderr.write(f"Failed to comment on issue: {error}\n")


def process_issue(issue: dict[str, Any], members_dir: Path) -> tuple[bool, str, Path | None]:
    user = str(issue.get("user") or "").strip()
    title = str(issue.get("title") or "")
    fields = parse_issue_body(issue.get("body"))
    mode = detect_mode(title, fields)
    checkbox_section = fields.get("추가할 항목") if mode == "add" else fields.get("수정할 항목")
    checked = checked_labels(checkbox_section)
    members = load_members(members_dir)
    path, data, body = find_member_by_github(members, user)
    resolved = path.resolve()
    if resolved.parent != members_dir.resolve():
        raise Rejected("멤버 파일 경로가 올바르지 않습니다.")
    assert_same_person(fields, data, path)
    original_github = data.get("github")
    original_permalink = data.get("permalink")
    updated, applied, skipped, changed_keys = apply_fields(data, mode, fields, checked, user)
    if updated.get("github") != original_github or updated.get("permalink") != original_permalink:
        raise Rejected("github 또는 permalink가 바뀌려 해서 중단했습니다.")
    roundtrip_ok(updated)
    original_text = path.read_text(encoding="utf-8")
    path.write_text(patch_member_file(original_text, updated, changed_keys), encoding="utf-8")
    comment = build_comment(True, path, applied, skipped, "")
    return True, comment, path


def write_success_comment(body: str) -> None:
    path = os.environ.get("MEMBER_APPLY_COMMENT")
    if path:
        Path(path).write_text(body, encoding="utf-8")
        return
    sys.stderr.write(body + "\n")


def run(issue_json: Path, members_dir: Path) -> int:
    issue = json.loads(issue_json.read_text(encoding="utf-8"))
    try:
        _changed, comment, _path = process_issue(issue, members_dir)
        write_success_comment(comment)
        return 0
    except Rejected as error:
        post_issue_comment(build_comment(False, None, [], [], str(error)))
        return 0
    except Exception as error:
        post_issue_comment(
            "자동 반영 중 오류가 났습니다. 관리자가 확인합니다.\n\n"
            f"`{type(error).__name__}: {error}`"
        )
        return 1


def self_test() -> None:
    body = """
### 이름 (English)

Soyeon Baek

### 이름 (한글)

백소연

### 멤버 페이지 주소

https://cnu-ants.github.io/members/soyeonb

### 추가할 항목

- [x] LinkedIn
- [x] 관심 분야 (Research interests)
- [ ] GitHub

### LinkedIn

https://www.linkedin.com/in/soyeon-baek

### 관심 분야

static analysis, Android
"""
    fields = parse_issue_body(body)
    assert fields["이름 (English)"] == "Soyeon Baek"
    assert "LinkedIn" in checked_labels(fields["추가할 항목"])
    assert normalize_github("https://github.com/SoyeonB/") == "soyeonb"
    assert (
        strip_simple_html(
            '<a href="https://www.linkedin.com/in/soyeon-baek" rel="nofollow">https://www.linkedin.com/in/soyeon-baek</a>'
        )
        == "https://www.linkedin.com/in/soyeon-baek"
    )

    with tempfile.TemporaryDirectory() as tmp:
        members_dir = Path(tmp)
        sample = members_dir / "soyeonb.md"
        sample.write_text(
            "---\nlayout: resume\nname: Soyeon Baek\nname_kor: 백소연\n"
            "github: soyeonb\npermalink: /members/soyeonb\n---\n",
            encoding="utf-8",
        )
        issue = {
            "user": "soyeonb",
            "title": "[Member] Add info: Soyeon Baek",
            "body": body,
        }
        changed, _comment, path = process_issue(issue, members_dir)
        assert changed and path == sample
        data, _body = split_front_matter(sample.read_text(encoding="utf-8"))
        assert data["linkedin"] == "https://www.linkedin.com/in/soyeon-baek"
        assert data["interests"] == ["static analysis", "Android"]
        assert data["github"] == "soyeonb"

        try:
            process_issue(
                {
                    "user": "mallory",
                    "title": "[Member] Add info: Soyeon Baek",
                    "body": body,
                },
                members_dir,
            )
            raise AssertionError("foreign author should be rejected")
        except Rejected:
            pass

        bad_name = body.replace("Soyeon Baek", "Someone Else", 1)
        try:
            process_issue(
                {
                    "user": "soyeonb",
                    "title": "[Member] Add info: Someone Else",
                    "body": bad_name,
                },
                members_dir,
            )
            raise AssertionError("wrong name should be rejected")
        except Rejected:
            pass

        js_body = body.replace("https://www.linkedin.com/in/soyeon-baek", "javascript:alert(1)")
        try:
            process_issue(
                {
                    "user": "soyeonb",
                    "title": "[Member] Add info: Soyeon Baek",
                    "body": js_body,
                },
                members_dir,
            )
            raise AssertionError("javascript URL should be rejected")
        except Rejected:
            pass

        for member_path, member_data, _member_body in load_members(MEMBERS_DIR):
            roundtrip_ok(member_data)

    with tempfile.TemporaryDirectory() as tmp:
        members_dir = Path(tmp)
        sample = members_dir / "soyeonb.md"
        original = (
            "---\nlayout: resume\nname: Soyeon Baek\nname_kor: 백소연\n"
            "github: soyeonb\npermalink: /members/soyeonb\n"
            "awards: [\n[한국정보과학회(KSC), 우수발표논문상, 2024],]\n---\n"
        )
        sample.write_text(original, encoding="utf-8")
        checkbox_only = """
### 이름 (English)

Soyeon Baek

### 이름 (한글)

백소연

### 멤버 페이지 주소

https://cnu-ants.github.io/members/soyeonb

### 추가할 항목

- [X] LinkedIn
- [ ] Google Scholar
- [ ] 수상 (Honors)

### LinkedIn

https://www.linkedin.com/in/soyeon-baek

### Google Scholar

https://scholar.google.com/citations?user=abcdefghijk

### 수상

한국정보과학회(KCC), 최우수상, 2024
"""
        changed, comment, path = process_issue(
            {
                "user": "soyeonb",
                "title": "[Member] Add info: Soyeon Baek",
                "body": checkbox_only,
            },
            members_dir,
        )
        text = path.read_text(encoding="utf-8")
        data, _body = split_front_matter(text)
        assert changed and path == sample
        assert data["linkedin"] == "https://www.linkedin.com/in/soyeon-baek"
        assert "scholar" not in data
        assert "awards: [\n[한국정보과학회(KSC), 우수발표논문상, 2024],]" in text
        assert "체크하지 않아 반영하지 않았습니다" in comment
        assert "github: soyeonb" in text
        assert "최우수상" not in text

    print("self-test ok")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-json", type=Path)
    parser.add_argument("--members-dir", type=Path, default=MEMBERS_DIR)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.issue_json:
        parser.error("--issue-json is required")
    return run(args.issue_json, args.members_dir)


if __name__ == "__main__":
    sys.exit(main())
