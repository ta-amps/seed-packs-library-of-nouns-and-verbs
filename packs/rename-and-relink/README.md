# Rename and relink

## What this pack lets workers do

A collection of nouns and verbs for renaming products, repositories and pages and rewriting
every reference and link to the new names. Renames leak: an old name survives in a status
message, a badge, a workflow name or a caption, and links keep working only because a redirect
happens to exist. Workers inventory every spelling of every old name at exact commits, plan
and make the rewrites in local copies, check every link without relying on a redirect, take
the owner's record of what they renamed on hosts, and sweep until no old name remains outside
an allowed context such as provenance or history. Each retired address gets a plain notice.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle and the rules: status lines and captions count, redirects never fix anything, a returning name is a finding |
| Reference types | Prose, links, identifiers, configuration, packages, checks, media, provenance and history, and places outside repositories |
| Variant rules | Every case, separator, plural and address form of a name, and hashed search for names never written down |
| Allowed contexts | Provenance fields, history written before the rename and the archive notice; everything else is a violation |
| Link rules | Reach every target without a redirect, record failures, list links the team does not control |
| Rename checks | 9 deterministic checks with 2 made-up good and 9 made-up bad sweeps, rechecked by `make check` |
| Templates | Rename map, reference inventory, rewrite plan, rewrite, link check, host rename record, old-name sweep and archive notice |
| Worked examples | A rename map for one repository and one site, and the notice at the retired address |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| build-inventory | agent, deterministic | Finds every variant of every old name in local copies at exact commits |
| plan-rewrites | agent | Turns each occurrence into an edit or a justified keep, and lists the owner's host acts |
| rewrite-references | agent | Edits a local copy and runs the repository's own checks; the result stays a patch |
| record-host-renames | owner | Records the repository, site and address renames carried out on hosts |
| check-links | agent, deterministic | Resolves every link and records redirects and failures |
| sweep-old-names | agent, deterministic | Decides clean, violations found or unknown |
| write-archive-notice | agent | Drafts a short notice for a retired address |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. A name that keeps coming back goes to
[findings to fixes](../findings-to-fixes/README.md); landing the rewrites follows
[release and verify](../release-and-verify/README.md).

## Worked examples

All made-up. A small program renames its tracker repository and its site, relying on no
redirect. The rename checks hold a clean sweep, where the only old names left are a changelog
line and a provenance field, and an honest sweep that still found an old name and a redirect.
The notice at the retired address says where everything went and that it will not forward.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- Searches find spellings, not meaning: a description that still implies the old name needs a reviewer.
- Text inside images and videos, and places outside the repositories, are listed for a person, not checked.
