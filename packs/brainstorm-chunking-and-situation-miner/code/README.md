# brainstorm_miner

Standard-library Python tools for splitting inline or block clipboard repeats, collapsing exact and
word-shingle near-duplicates, chunking unstructured notes into content-addressed records, and ranking
candidate seed-pack category gaps.

## Commands

```bash
python3 -m brainstorm_miner dedup raw_notes.txt
python3 -m brainstorm_miner chunk raw_notes.txt
python3 -m brainstorm_miner mine raw_notes.txt --near-dup-threshold 0.85
make check
```
