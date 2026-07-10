# `Licenses` sheet — column layout

`setupSheet()` in `Code.gs` creates this header row automatically. If you
prefer to build it by hand (or in Excel first), use exactly these columns
in this order:

| # | Column | Meaning | Set by |
|---|--------|---------|--------|
| A | **Code** | The license code, e.g. `TRAV-AB12-CD34-EF56` | generator |
| B | **PlanDays** | Days of use: 1, 7, 30, 90, 365, or custom | you / generator |
| C | **MachineID** | PC the code is locked to (empty until first activation) | auto on activate |
| D | **UID** | Your label for the user (name / phone / telegram) | you (optional) |
| E | **IssuedAt** | When the code was generated (YYYY-MM-DD) | generator |
| F | **ActivatedAt** | First activation date (YYYY-MM-DD) | auto on activate |
| G | **ExpiryAt** | Last valid day = ActivatedAt + PlanDays (YYYY-MM-DD) | auto on activate |
| H | **Status** | `UNUSED` → `ACTIVE` → `EXPIRED` / `REVOKED` | auto / you |
| I | **Note** | Free note (paid, trial, …) | you (optional) |

## Example rows

| Code | PlanDays | MachineID | UID | IssuedAt | ActivatedAt | ExpiryAt | Status | Note |
|------|----------|-----------|-----|----------|-------------|----------|--------|------|
| TRAV-AB12-CD34-EF56 | 30 | 97E07-B9788-1EA63-832F2 | Sok Dara | 2026-06-10 | 2026-06-10 | 2026-07-10 | ACTIVE | paid |
| TRAV-GH78-IJ90-KL12 | 7 |  | trial user | 2026-07-01 |  |  | UNUSED | 7-day trial |
| TRAV-MN34-OP56-QR78 | 365 | 11111-22222-33333-44444 | VIP |2026-01-01 | 2026-01-01 | 2027-01-01 | REVOKED | refunded |

Row 1 shows the strict rule: a 30-day code activated **2026-06-10** has
`ExpiryAt = 2026-07-10`. It works through **10 July 2026** and stops on
**11 July 2026**.

## Manual Excel/Sheets code generator (no Apps Script)

If you want to pre-make codes in a spreadsheet cell, this formula builds a
`TRAV-XXXX-XXXX-XXXX` code from safe characters (no confusing 0/O/1/I):

```
=CONCATENATE("TRAV-",
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),"-",
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),"-",
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1),
 MID("ABCDEFGHJKLMNPQRSTUVWXYZ23456789",RANDBETWEEN(1,31),1))
```

> The Apps Script `generateCode()` / the sidebar button is preferred — it
> also writes the row, so activation and the signature "just work".
