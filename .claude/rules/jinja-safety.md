---
paths:
  - "src/api/templates/**"
---

# Jinja2 Template Safety

## Never use `| safe` for user-controlled data

`{{ var | safe }}` disables Jinja2 autoescaping and is an XSS vector. Use `{{ var | tojson }}` to embed data in `<script>` blocks -- it produces valid JSON and escapes HTML-special characters. Reserve `| safe` for trusted static markup only.
