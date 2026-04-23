# Zeemap — seeds

Hermes writes durable seeds here — decisions, ideas, research, beliefs,
questions — accumulated across conversations. Each file is plain markdown
with YAML frontmatter, including a free-form `zone:` label.

Browse chronologically:
```
ls -lt ~/.hermes/skills/productivity/zeemap/data/
```

Browse by zone:
```
grep -l '^zone: health' ~/.hermes/skills/productivity/zeemap/data/
```

Show the current zone vocabulary:
```
grep -h '^zone:' ~/.hermes/skills/productivity/zeemap/data/*.md | sort | uniq -c
```

See `~/.hermes/skills/productivity/zeemap/SKILL.md` for the capture rules.
