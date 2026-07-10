# `Licenses` sheet — column layout

`setupSheet()` in `Code.gs` creates this header row automatically. If you
prefer to build it by hand (or in Excel first), use exactly these columns
in this order:

| # | Column | Meaning | Set by |
|---|--------|---------|--------|
| A | **License_Key** | The code, e.g. `TRAV-AB12-CD34-EF56` | generator |
| B | **Duration** | Days of use: 1, 7, 30, 90, 365, or custom | you / generator |
| C | **Device_UID** | PC the code is locked to (empty until first activation) | auto on activate |
| D | **Phone_Model** | The user's PC/device model | auto on activate |
| E | **Status** | `UNUSED` → `ACTIVE` → `EXPIRED` / `REVOKED` | auto / you |
| F | **Activation_Date** | First activation date (YYYY-MM-DD) | auto on activate |
| G | **Expiry_Date** | Last valid day = Activation_Date + Duration | auto on activate |
| H | **Owner** | The user's name (shown inside the app) | you |

`setupSheet()` writes exactly this header row, so it matches the app.

## Example rows

| License_Key | Duration | Device_UID | Phone_Model | Status | Activation_Date | Expiry_Date | Owner |
|------|----|-----|-----|--------|------------|------------|------|
| TRAV-AB12-CD34-EF56 | 30 | 97E07-B9788-1EA63-832F2 | ASUS TUF F15 | ACTIVE | 2026-06-10 | 2026-07-10 | Sok Dara |
| TRAV-GH78-IJ90-KL12 | 7 |  |  | UNUSED |  |  | trial user |
| TRAV-MN34-OP56-QR78 | 365 | 11111-22222-33333-44444 | HP Pavilion | REVOKED | 2026-01-01 | 2027-01-01 | VIP (refunded) |

Row 1 shows the strict rule: a 30-day code activated **2026-06-10** has
`Expiry_Date = 2026-07-10`. It works through **10 July 2026** and stops on
**11 July 2026**. The **Owner** ("Sok Dara") appears in the app header/status.

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
