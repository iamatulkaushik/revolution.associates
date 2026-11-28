# INTEGRATION AND UAT

## Git setup (you, Day 0)
```
git checkout capp_upgrades && git pull
git checkout -b capp_upgrades/ai1-foundation capp_upgrades
git checkout -b capp_upgrades/ai2-direct     capp_upgrades
git checkout -b capp_upgrades/ai3-entry      capp_upgrades
```
Give each AI: its track file, `00_MASTER_PLAN.md`, `01_COMMON_RULES.md`, and repo access to its own branch only.

## Merge order and protocol
1. **C1 (Day 1)** review AI-2's `INVENTORY.md`. No merge.
2. **C2 (Day 3)** merge AI-1 into `capp_upgrades`. AI-2 and AI-3 then `git rebase capp_upgrades`. AI-1 runs `makemigrations`, commits with `git add -f`.
3. **C3 (Day 5)** merge AI-3, then AI-2. After each: AI-1 runs the full gate (`01_COMMON_RULES.md` section 5), regenerates the single migration, fixes conflicts only in files it owns.
4. Conflict in a file you do not own = stop, send to the owner of that file.

## Merge gate (all must pass)
`py_compile` clean · `manage.py check` clean · `makemigrations --check` clean · `migrate --plan` shows only expected steps · `manage.py test Capp` green · matrix test green · duplicate URL-name check empty.

## UAT script (you, about 2 hours, Day 5)
Use two companies. Company X = DIRECT, copper. Company Y = ASSOCIATE, copper. Each has an owner and one operator (attendance flag only).

| # | Step | Expected |
|---|---|---|
| 1 | Sapp: create X with mode Direct, Y with mode Associate | Mode shown in Capp header badge |
| 2 | X owner: set statutory registrations | Gates update; challans appear only for registered schemes |
| 3 | Y owner: open statutory / challans / process payroll URLs | Blocked with message |
| 4 | Both: add employees until copper limit (150) | 151st blocked with plan message; existing untouched |
| 5 | Y operator: add attendance for a month | Saved; audit log shows operator name |
| 6 | Y operator: try employees add (no flag) | Denied |
| 7 | X owner: run month → process → finalize → paid | Status transitions; reopen rules respected |
| 8 | Y: associate processes and approves batch in Aapp | Y owner and operator can now download salary sheet, slip, abstract |
| 9 | Y before approval: try download | "Batch not finalized yet" |
| 10 | Y after PROCESSED: operator edits attendance | Locked |
| 11 | Open another company's slip URL | 404 |
| 12 | Suspend operator | Cannot log in |
| 13 | Raise X to silver in Sapp | Limit rises without code change |
| 14 | Import the owner's sample workbook (employees, then ATT) | Preview then confirm; re-import updates |

## Release and rollback
- Release: merge `capp_upgrades` → `main` only after UAT. Run `pip install -r requirements.txt`, `migrate`, `seed_plan_limits`.
- Rollback: migrations in this upgrade only add fields/tables (no drops). Revert the merge commit; unused tables are harmless.
