# -*- coding: utf-8 -*-
import io, markdown, re, datetime

src = r'D:\github项目\blog\textworld-bug-fix.md'
out = r'D:\github项目\blog\textworld-bug-fix.html'
text = io.open(src, encoding='utf-8').read()

# 去掉第一个 H1（用自定义头部展示标题）
lines = text.split('\n')
title = lines[0].lstrip('# ').strip()
body_md = '\n'.join(lines[1:]).lstrip('\n')

html_body = markdown.markdown(body_md, extensions=['fenced_code', 'tables', 'sane_lists'])

CSS = """
:root{
  --ink:#1d1d1f; --sub:#6e6e73; --bg:#fbfbfd; --card:#ffffff;
  --code-bg:#f5f5f7; --line:#e3e3e6; --accent:#0071e3;
}
*{box-sizing:border-box;}
html{-webkit-text-size-adjust:100%;}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display",
    "Segoe UI",Roboto,"Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif;
  line-height:1.75; font-size:17px; letter-spacing:-0.01em;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:740px; margin:0 auto; padding:72px 24px 96px;}
header.hero{margin-bottom:40px;}
h1.title{
  font-size:38px; line-height:1.18; font-weight:700; letter-spacing:-0.025em;
  margin:0 0 16px; color:var(--ink);
}
.meta{font-size:14px; color:var(--sub); display:flex; gap:14px; flex-wrap:wrap; align-items:center;}
.meta a{color:var(--accent); text-decoration:none;}
.meta .dot{width:3px;height:3px;border-radius:50%;background:var(--sub);display:inline-block;}
h2{
  font-size:25px; font-weight:700; letter-spacing:-0.02em;
  margin:48px 0 14px; padding-top:8px; color:var(--ink);
}
h3{font-size:19px; font-weight:600; margin:32px 0 10px;}
p{margin:14px 0;}
a{color:var(--accent); text-decoration:none;}
a:hover{text-decoration:underline;}
strong{font-weight:650;}
ul,ol{padding-left:24px; margin:14px 0;}
li{margin:7px 0;}
blockquote{
  margin:22px 0; padding:6px 20px; border-left:3px solid var(--line);
  color:var(--sub); font-size:15.5px;
}
blockquote p{margin:8px 0;}
code{
  font-family:"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
  font-size:0.86em; background:var(--code-bg);
  padding:2px 6px; border-radius:6px; color:#3a3a3c;
}
pre{
  background:var(--code-bg); border:1px solid var(--line); border-radius:12px;
  padding:16px 18px; overflow-x:auto; margin:20px 0; line-height:1.6;
}
pre code{background:none; padding:0; font-size:13.5px; color:#2b2b2d; border-radius:0;}
hr{border:none; border-top:1px solid var(--line); margin:44px 0;}
table{border-collapse:collapse; width:100%; margin:20px 0; font-size:15px;}
th,td{border:1px solid var(--line); padding:8px 12px; text-align:left;}
th{background:var(--code-bg); font-weight:600;}
footer{margin-top:64px; padding-top:24px; border-top:1px solid var(--line);
  font-size:14px; color:var(--sub);}
footer a{color:var(--accent);}
@media (max-width:600px){
  .wrap{padding:48px 18px 72px;}
  h1.title{font-size:29px;} h2{font-size:22px;} body{font-size:16px;}
}
"""

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <h1 class="title">{title}</h1>
  <div class="meta">
    <a href="https://github.com/microsoft/TextWorld/pull/377" target="_blank" rel="noopener">PR #377 · 已合并</a>
    <span class="dot"></span>
    <span>microsoft/TextWorld</span>
    <span class="dot"></span>
    <span>Daizhi Liao</span>
  </div>
</header>
{body}
<footer>
  <a href="index.html">&larr; Blog</a> &nbsp;&middot;&nbsp; More on
  <a href="https://github.com/dafahaha" target="_blank" rel="noopener">github.com/dafahaha</a>.
</footer>
</div>
</body>
</html>
""".format(title=title, css=CSS, body=html_body)

io.open(out, 'w', encoding='utf-8', newline='').write(html)
print('HTML written:', out, len(html), 'bytes')
