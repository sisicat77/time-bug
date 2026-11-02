#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 README.md / README.en.md 转成 index.html / index.en.html。"""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def convert(md: str) -> str:
    lines = md.splitlines()

    # 语言切换行只给 README 用；页面顶部已经有切换链接，正文里不重复。
    if lines and lines[0].strip().startswith("[中文](README.md)"):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)

    out: list[str] = []
    i = 0
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    para: list[str] = []
    table: list[str] = []
    first_figure = True

    def flush_para() -> None:
        nonlocal para
        if para:
            text = " ".join(para).strip()
            if text:
                out.append(f"<p>{inline(text)}</p>")
            para = []

    def flush_table() -> None:
        nonlocal table
        if not table:
            return
        rows = [r for r in table if r.strip()]
        if len(rows) >= 2:
            header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
            sep = [c.strip() for c in rows[1].strip().strip("|").split("|")]

            def cls(idx: int) -> str:
                return ' class="num"' if idx < len(sep) and sep[idx].endswith(":") else ""

            out.append('<div class="table-wrap"><table><thead><tr>')
            for idx, c in enumerate(header):
                out.append(f"<th{cls(idx)}>{inline(c)}</th>")
            out.append("</tr></thead><tbody>")
            for r in rows[2:]:
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                out.append("<tr>")
                for idx, c in enumerate(cells):
                    out.append(f"<td{cls(idx)}>{inline(c)}</td>")
                out.append("</tr>")
            out.append("</tbody></table></div>")
        table = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if in_code:
            if stripped.startswith("```"):
                code = html.escape("\n".join(code_lines), quote=False)
                lang = f' class="language-{code_lang}"' if code_lang else ""
                out.append(f"<pre><code{lang}>{code}</code></pre>")
                in_code = False
                code_lines = []
                code_lang = ""
            else:
                code_lines.append(line)
            i += 1
            continue

        if stripped.startswith("```"):
            flush_para()
            flush_table()
            in_code = True
            code_lang = stripped[3:].strip()
            i += 1
            continue

        if not stripped:
            flush_para()
            flush_table()
            i += 1
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m:
            flush_para()
            flush_table()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if stripped == "---":
            flush_para()
            flush_table()
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            flush_para()
            flush_table()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            text = " ".join(q for q in quote if q)
            out.append(f"<blockquote>{inline(text)}</blockquote>")
            continue

        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            flush_para()
            flush_table()
            alt, src = m.group(1), m.group(2)
            cls = ' class="hero"' if first_figure else ""
            out.append(
                f'<figure{cls}><a href="{src}" target="_blank" rel="noopener">'
                f'<img src="{src}" alt="{html.escape(alt, quote=True)}" loading="lazy"></a>'
                f"<figcaption>{inline(alt)}</figcaption></figure>"
            )
            first_figure = False
            i += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_para()
            table.append(stripped)
            i += 1
            continue

        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            flush_para()
            flush_table()
            items = []
            while i < len(lines):
                s = lines[i].strip()
                mm = re.match(r"^[-*]\s+(.*)$", s)
                if not mm:
                    break
                items.append(f"<li>{inline(mm.group(1))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            flush_para()
            flush_table()
            items = []
            while i < len(lines):
                s = lines[i].strip()
                mm = re.match(r"^(\d+)\.\s+(.*)$", s)
                if not mm:
                    break
                items.append(f"<li>{inline(mm.group(2))}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        para.append(stripped)
        i += 1

    flush_para()
    flush_table()
    return "\n".join(out)


def embed_images(html_text: str) -> str:
    """把 figures/*.png 内嵌成 data URI，让页面单文件也能看图。"""
    for name in ("phase.png", "spiral.png", "arrow.png"):
        path = ROOT / "figures" / name
        if not path.exists():
            continue
        data = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        html_text = html_text.replace(f'src="figures/{name}"', f'src="{data}"')
    return html_text


TEMPLATE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="author" content="sisicat">
<meta name="color-scheme" content="light">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{og_image}">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<style>
  :root{
    --paper:#F7F3EC;
    --paper-2:#F1ECE2;
    --ink:#2F2B27;
    --muted:#7A7168;
    --faint:#DCD3C5;
    --grid:#E6DFD3;
    --clay:#B78E6E;
    --serif:"Noto Serif SC","Noto Serif CJK SC","Songti SC",SimSun,serif;
    --sans:"Noto Sans SC","Noto Sans CJK SC","PingFang SC","Microsoft YaHei",sans-serif;
  }
  html[lang="en"]{
    --serif:"Iowan Old Style","Palatino Linotype","Book Antiqua",Georgia,serif;
    --sans:"Avenir Next","Segoe UI",Helvetica,Arial,sans-serif;
  }
  *{box-sizing:border-box}
  html{background:var(--paper)}
  body{
    margin:0;
    background:var(--paper);
    color:var(--ink);
    font-family:var(--serif);
    font-size:17px;
    line-height:1.95;
    -webkit-font-smoothing:antialiased;
    text-rendering:optimizeLegibility;
  }
  html[lang="en"] body{font-size:18px;line-height:1.82}
  .page{max-width:760px;margin:0 auto;padding:72px 28px 96px}
  .topbar{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:18px}
  .kicker{
    font-family:var(--sans);
    font-size:11px;letter-spacing:.22em;color:var(--muted);
  }
  .lang{
    font-family:var(--sans);font-size:11px;letter-spacing:.12em;
    color:var(--muted);text-decoration:none;border-bottom:1px solid var(--faint);
    padding-bottom:2px;white-space:nowrap;
  }
  .lang:hover{color:var(--clay);border-bottom-color:var(--clay)}
  .prose h1{
    font-size:42px;line-height:1.24;font-weight:600;letter-spacing:.01em;
    margin:0 0 22px;
  }
  html[lang="en"] .prose h1{font-size:40px;line-height:1.16;letter-spacing:-.01em}
  .prose h1::after{
    content:"";display:block;width:52px;height:1px;background:var(--clay);
    margin-top:26px;opacity:.65;
  }
  .prose blockquote{
    margin:0 0 30px;padding:0 0 0 18px;border-left:2px solid var(--faint);
    color:#5F574E;font-size:16.5px;line-height:1.85;
  }
  .prose blockquote p{margin:0}
  .prose p{margin:0 0 1.35em}
  .prose h2{
    font-size:25px;line-height:1.4;font-weight:600;letter-spacing:.01em;
    margin:3.2em 0 1.1em;padding-top:1.1em;border-top:1px solid var(--grid);
  }
  html[lang="en"] .prose h2{font-size:24px;line-height:1.35}
  .prose h3{
    font-size:19px;font-weight:600;margin:2.4em 0 .8em;color:#453F38;
  }
  .prose strong{font-weight:600;color:#241F1B}
  .prose a{color:var(--clay);text-decoration:none;border-bottom:1px solid rgba(183,142,110,.35)}
  .prose a:hover{border-bottom-color:var(--clay)}
  .prose ul,.prose ol{margin:0 0 1.4em;padding-left:1.4em}
  .prose li{margin:.45em 0}
  .prose li::marker{color:var(--clay)}
  .prose hr{border:0;height:1px;background:var(--grid);margin:3em 0}
  .prose code{
    font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
    font-size:.88em;background:var(--paper-2);padding:.15em .38em;border-radius:3px;
  }
  .prose pre{
    background:var(--paper-2);border-left:2px solid var(--faint);
    padding:16px 18px;overflow-x:auto;margin:0 0 1.6em;
    font-size:13.5px;line-height:1.7;
  }
  .prose pre code{background:none;padding:0;font-size:inherit}
  .prose figure{
    width:min(1040px, calc(100vw - 48px));
    margin:2.2em 0 2.6em;
    margin-left:calc((100% - min(1040px, 100vw - 48px)) / 2);
  }
  .prose figure img{display:block;width:100%;height:auto;border-radius:2px}
  .prose figure a{display:block;border:0}
  .prose figure a:hover{border:0}
  .prose figure.hero{margin-top:2.4em;margin-bottom:2.8em}
  .prose figcaption{
    font-family:var(--sans);
    font-size:12px;color:var(--muted);line-height:1.7;margin-top:12px;
    text-align:center;
  }
  .table-wrap{overflow-x:auto;margin:0 0 1.8em}
  .prose table{
    width:100%;border-collapse:collapse;
    font-family:var(--sans);
    font-size:13px;line-height:1.65;
  }
  .prose th,.prose td{
    padding:9px 10px;border-bottom:1px solid var(--grid);text-align:left;white-space:nowrap;
  }
  .prose th{font-weight:600;color:#4A433C;border-bottom-color:var(--faint)}
  .prose td.num,.prose th.num{text-align:right;font-variant-numeric:tabular-nums}
  .prose tbody tr:nth-child(even){background:rgba(230,223,211,.28)}
  html[lang="en"] .prose table{font-size:12.5px}
  html[lang="en"] .prose th, html[lang="en"] .prose td{white-space:normal}
  footer{
    margin-top:72px;padding-top:22px;border-top:1px solid var(--grid);
    display:flex;justify-content:space-between;gap:20px;
    font-family:var(--sans);
    font-size:11.5px;color:var(--muted);letter-spacing:.02em;
  }
  @media (max-width:640px){
    body{font-size:16px;line-height:1.9}
    .page{padding:44px 20px 64px}
    .prose h1{font-size:32px}
    html[lang="en"] .prose h1{font-size:30px}
    .prose h2{font-size:22px}
    .prose h3{font-size:18px}
    footer{flex-direction:column;gap:6px}
  }
</style>
</head>
<body>
<div class="page">
  <div class="topbar">
    <div class="kicker">{kicker}</div>
    <a class="lang" href="{lang_href}">{lang_label}</a>
  </div>
  <main class="prose">
{body}
  </main>
  <footer>
    <span>{footer_left}</span>
    <span>sisicat · 2026</span>
  </footer>
</div>
</body>
</html>
"""


def build_page(src: str, out: str, **ctx: str) -> None:
    body = embed_images(convert((ROOT / src).read_text(encoding="utf-8")))
    html_text = TEMPLATE
    values = {"body": body, **ctx}
    for key, value in values.items():
        html_text = html_text.replace("{" + key + "}", value)
    (ROOT / out).write_text(html_text, encoding="utf-8")
    print(f"已写出 {out}  ({len(html_text)} 字符)")


def main() -> None:
    build_page(
        "README.md", "index.html",
        lang="zh-CN",
        title="人类是 Bug，时间是变量 · 一个微型思想实验",
        description="一个关于 AI 内禀时间的微型思想实验：闭合、耗散、记忆与 Hook，如何让一条轨迹长出不回头的时间箭头。",
        kicker="一个微型思想实验",
        lang_href="index.en.html",
        lang_label="EN",
        footer_left="代码与图表 MIT · 文字 CC BY-NC-SA 4.0",
        og_image="preview.png",
    )
    build_page(
        "README.en.md", "index.en.html",
        lang="en",
        title="Humans Are a Bug, Time Is a Variable · A Miniature Thought Experiment",
        description="A miniature thought experiment on AI's intrinsic time: closure, dissipation, memory, and a Hook — and how a trajectory grows an arrow of time.",
        kicker="A MINIATURE THOUGHT EXPERIMENT",
        lang_href="index.html",
        lang_label="中文",
        footer_left="Code & figures MIT · Text CC BY-NC-SA 4.0",
        og_image="preview-en.png",
    )


if __name__ == "__main__":
    main()
