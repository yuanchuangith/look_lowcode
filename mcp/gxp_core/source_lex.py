from __future__ import annotations

import bisect
import re
from typing import NamedTuple


BACKTICK = chr(96)
SPECIAL = re.compile(r'//|/\*|@"|"""|["\x27\x60]|/(?![/*])')
WORDS = re.compile(r'[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|[{}\[\]();,.:]|>>>=|<<=|>>=|\*\*=|&&=|\|\|=|\?\?=|[+*/%&|^\-]=|=>|\?\.|===|!==|==|!=|\?\?|&&|\|\||\+\+|--|[^\s]', re.UNICODE)
QUOTED = {
    "'": re.compile(r"'(?:\\[\s\S]|[^'\\\r\n])*'"),
    '"': re.compile(r'"(?:\\[\s\S]|[^"\\\r\n])*"'),
    '@"': re.compile(r'@"(?:""|[^"])*"'),
}


class Token(NamedTuple):
    value: str
    start: int
    end: int
    kind: str = "code"


def _blank(text: str) -> str:
    if "\n" not in text and "\r" not in text:
        return " " * len(text)
    return re.sub(r"[^\r\n]+", lambda match: " " * len(match.group()), text)


def _template_end(text: str, start: int, *, quote: str = BACKTICK) -> int | None:
    cursor = start + 1
    depth = 0
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if not depth and char == quote:
            return cursor + 1
        if not depth and (text.startswith("$" + "{", cursor) or quote == '"' and char == "{"):
            if quote == '"' and text.startswith("{{", cursor):
                cursor += 2
                continue
            depth = 1
            cursor += 2 if quote == BACKTICK else 1
            continue
        if depth:
            if char == BACKTICK:
                nested = _template_end(text, cursor)
                if nested is None:
                    return None
                cursor = nested
                continue
            if char in "'\"":
                match = QUOTED[char].match(text, cursor)
                if not match:
                    return None
                cursor = match.end()
                continue
            if text.startswith("//", cursor):
                end = text.find("\n", cursor)
                if end < 0:
                    return None
                cursor = end
                continue
            if text.startswith("/*", cursor):
                end = text.find("*/", cursor + 2)
                if end < 0:
                    return None
                cursor = end + 2
                continue
            if char == "/" and (text[max(start, cursor - 1):cursor] in "(=,[" or not text[start:cursor].strip()):
                end = _regex_end(text, cursor)
                if end:
                    cursor = end
                    continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
        cursor += 1
    return None



def _regex_end(text: str, start: int) -> int | None:
    cursor = start + 1
    bracket = False
    while cursor < len(text) and text[cursor] not in "\r\n":
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "[":
            bracket = True
        elif char == "]":
            bracket = False
        elif char == "/" and not bracket:
            cursor += 1
            while cursor < len(text) and text[cursor].isalpha():
                cursor += 1
            return cursor
        cursor += 1
    return None


class LexedSource:
    def __init__(self, text: str, *, language: str = "typescript"):
        self.text = text
        self.errors: list[str] = []
        self.strings: list[Token] = []
        self.line_starts = [0, *(match.end() for match in re.finditer("\n", text))]
        clean_parts = []
        code_parts = []
        cursor = 0
        while match := SPECIAL.search(text, cursor):
            start = match.start()
            marker = match.group()
            end = None
            kind = "string"
            if marker == "//":
                end = text.find("\n", match.end())
                end = len(text) if end < 0 else end
                kind = "comment"
            elif marker == "/*":
                close = text.find("*/", match.end())
                end = close + 2 if close >= 0 else None
                kind = "comment"
            elif marker == BACKTICK:
                end = _template_end(text, start)
            elif marker == '"""':
                close = text.find('"""', match.end())
                end = close + 3 if close >= 0 else None
                if language == "csharp":
                    kind = "opaque"
            elif marker == "/":
                previous = text[max(0, start - 128):start].rstrip()[-1:]
                if language != "csharp" and (not previous or previous in "=([{,:;!?&|" or re.search(r"\breturn\s*$", text[max(0, start - 12):start])):
                    end = _regex_end(text, start)
                    kind = "regex"
                if end is None:
                    clean_parts.append(text[cursor:match.end()])
                    code_parts.append(text[cursor:match.end()])
                    cursor = match.end()
                    continue
            elif marker == '"' and language == "csharp" and start and text[start - 1] == "$":
                end = _template_end(text, start, quote='"')
            else:
                quoted = QUOTED[marker].match(text, start)
                end = quoted.end() if quoted else None
            if end is None:
                self.errors.append(f"unclosed_{kind}:{self.line(start)}")
                end = len(text)
            clean_parts.extend((text[cursor:start], text[start:end] if kind == "string" else _blank(text[start:end])))
            code_parts.extend((text[cursor:start], _blank(text[start:end])))
            if kind == "string":
                self.strings.append(Token(text[start:end], start, end, "string"))
            elif kind == "opaque":
                self.errors.append(f"unsupported_raw_string:{self.line(start)}")
            cursor = end
        self.clean = "".join((*clean_parts, text[cursor:]))
        self.code = "".join((*code_parts, text[cursor:]))
        self._tokens: list[Token] | None = None
        self._pairs: dict[int, int] | None = None

    def line(self, offset: int) -> int:
        return bisect.bisect_right(self.line_starts, offset)

    @property
    def tokens(self) -> list[Token]:
        if self._tokens is None:
            self._tokens = [Token(match.group(), match.start(), match.end()) for match in WORDS.finditer(self.code)]
            self._tokens.extend(self.strings)
            self._tokens.sort(key=lambda item: item.start)
        return self._tokens

    @property
    def pairs(self) -> dict[int, int]:
        if self._pairs is None:
            pairs = {}
            stack = []
            closers = {")": "(", "]": "[", "}": "{"}
            for index, token in enumerate(self.tokens):
                if token.kind != "code":
                    continue
                if token.value in ("(", "[", "{"):
                    stack.append(index)
                elif token.value in closers:
                    if stack and self.tokens[stack[-1]].value == closers[token.value]:
                        start = stack.pop()
                        pairs[start] = index
                        pairs[index] = start
                    else:
                        self.errors.append(f"unbalanced_delimiter:{self.line(token.start)}")
            if stack:
                self.errors.append("unclosed_delimiter")
            self._pairs = pairs
        return self._pairs


def string_value(token: Token) -> str:
    value = token.value
    if value.startswith('@"'):
        return value[2:-1].replace('""', '"')
    return value[1:-1]


def expression_end(tokens: list[Token], pairs: dict[int, int], start: int) -> int:
    cursor = start
    while cursor < len(tokens):
        value = tokens[cursor].value
        if tokens[cursor].kind == "code" and value in (",", ";", "}", ")", "]", "export", "const", "let", "var"):
            break
        if tokens[cursor].kind == "code" and value in ("(", "[", "{"):
            if cursor not in pairs:
                break
            cursor = pairs[cursor] + 1
        else:
            cursor += 1
    return cursor


def split_arguments(tokens: list[Token], pairs: dict[int, int], start: int, end: int) -> list[tuple[int, int]]:
    result = []
    cursor = start
    begin = start
    angle_depth = 0
    while cursor < end:
        value = tokens[cursor].value
        if value == "<":
            angle_depth += 1
        elif value == ">":
            angle_depth = max(0, angle_depth - 1)
        if value == "," and not angle_depth:
            result.append((begin, cursor))
            begin = cursor + 1
        if value in ("(", "[", "{") and cursor in pairs:
            cursor = pairs[cursor] + 1
        else:
            cursor += 1
    if begin < end:
        result.append((begin, end))
    return result
