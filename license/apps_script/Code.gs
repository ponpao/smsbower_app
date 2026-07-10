/****************************************************************************
 * TRAVKOD CODEs — License Server (Google Apps Script, bound to a Sheet)
 * ==========================================================================
 * Backs the Video Visualizer license gate AND the Keyadmin Flutter app.
 *
 * SETUP (see apps_script/README_SETUP.md for the full walk-through):
 *   1. Create a Google Sheet, Extensions ▸ Apps Script, paste this file.
 *   2. Add a file "Sidebar.html" (from apps_script/Sidebar.html).
 *   3. Set LICENSE_SECRET (== TRAVKOD_LICENSE_SECRET in license_client.py)
 *      and ADMIN_KEY (a private password for the admin app / sidebar).
 *   4. Run setupSheet() once (creates headers).
 *   5. Deploy ▸ New deployment ▸ Web app ▸ Execute as: Me ▸ Access: Anyone.
 *      Copy the /exec URL into WEB_APP_URL in license_client.py and into the
 *      Keyadmin Flutter app.
 ***************************************************************************/

// ==== CONFIG — CHANGE THESE ====
var LICENSE_SECRET = 'CHANGE-ME-to-a-long-random-secret-2026'; // == Python
var ADMIN_KEY      = 'CHANGE-ME-admin-password';               // admin only
var SHEET_NAME     = 'Licenses';
// Days counted from the activation date. expiry = activationDate + planDays,
// and the client allows use while today <= expiry (one day past = blocked).

// Column order (1-based). Keep in sync with setupSheet().
var COL = {CODE:1, PLAN:2, MACHINE:3, UID:4, ISSUED:5, ACTIVATED:6,
          EXPIRY:7, STATUS:8, NOTE:9};

// -------------------------------------------------------------------------
// Web entry points
// -------------------------------------------------------------------------

function doPost(e) {
  var out;
  try {
    var body = JSON.parse(e.postData.contents || '{}');
    out = route(body);
  } catch (err) {
    out = {ok: false, reason: 'server_error', detail: String(err)};
  }
  return ContentService.createTextOutput(JSON.stringify(out))
      .setMimeType(ContentService.MimeType.JSON);
}

// GET is used by the Keyadmin app for admin actions (list/generate/revoke)
// and as a health check. Client validate/activate go through POST.
function doGet(e) {
  var out;
  try {
    out = route(e.parameter || {});
  } catch (err) {
    out = {ok: false, reason: 'server_error', detail: String(err)};
  }
  return ContentService.createTextOutput(JSON.stringify(out))
      .setMimeType(ContentService.MimeType.JSON);
}

function route(p) {
  var action = p.action || '';
  switch (action) {
    case 'activate': return clientCheck(p.code, p.machine_id, true);
    case 'validate': return clientCheck(p.code, p.machine_id, false);
    case 'ping':     return {ok: true, server_date: today()};
    // ---- admin actions require ADMIN_KEY ----
    case 'generate': return admin(p) || generateCode(p);
    case 'revoke':   return admin(p) || revokeCode(p);
    case 'unrevoke': return admin(p) || setStatus(p.code, 'ACTIVE');
    case 'reset_pc': return admin(p) || resetMachine(p.code);
    case 'list':     return admin(p) || listLicenses();
    default:         return {ok: false, reason: 'unknown_action'};
  }
}

function admin(p) {   // returns an error object if the admin key is wrong
  if ((p.admin_key || '') !== ADMIN_KEY) {
    return {ok: false, reason: 'forbidden'};
  }
  return null;
}

// -------------------------------------------------------------------------
// Client: activate / validate
// -------------------------------------------------------------------------

function clientCheck(code, machine, isActivate) {
  code = String(code || '').trim().toUpperCase();
  machine = String(machine || '').trim();
  if (!code || !machine) return {ok: false, reason: 'invalid_code'};

  var sh = sheet();
  var row = findRow(sh, code);
  if (row < 0) return {ok: false, reason: 'invalid_code'};

  var rng = sh.getRange(row, 1, 1, COL.NOTE);
  var v = rng.getValues()[0];
  var status = String(v[COL.STATUS - 1] || 'UNUSED').toUpperCase();
  if (status === 'REVOKED') return {ok: false, reason: 'revoked'};

  var boundMachine = String(v[COL.MACHINE - 1] || '').trim();
  var planDays = Number(v[COL.PLAN - 1] || 0);

  if (!boundMachine) {
    // first activation: bind to this PC and stamp dates
    if (!isActivate) return {ok: false, reason: 'invalid_code'};
    var act = new Date();
    var exp = addDays(act, planDays);
    sh.getRange(row, COL.MACHINE).setValue(machine);
    sh.getRange(row, COL.ACTIVATED).setValue(fmt(act));
    sh.getRange(row, COL.EXPIRY).setValue(fmt(exp));
    sh.getRange(row, COL.STATUS).setValue('ACTIVE');
    return reply(machine, fmt(exp), 'ACTIVE', planDays);
  }

  if (boundMachine !== machine) {
    return {ok: false, reason: 'code_used_on_another_pc'};
  }

  var expiry = String(v[COL.EXPIRY - 1] || '');
  expiry = normalizeDate(expiry);
  if (!expiry) {   // safety: recompute if missing
    var a = normalizeDate(String(v[COL.ACTIVATED - 1] || '')) || today();
    expiry = fmt(addDays(new Date(a), planDays));
    sh.getRange(row, COL.EXPIRY).setValue(expiry);
  }
  if (today() > expiry) {
    sh.getRange(row, COL.STATUS).setValue('EXPIRED');
    return {ok: false, reason: 'expired', expiry: expiry};
  }
  return reply(machine, expiry, 'ACTIVE', planDays);
}

function reply(machine, expiry, status, planDays) {
  return {
    ok: true, machine_id: machine, expiry: expiry, status: status,
    plan_days: planDays, server_date: today(),
    sig: sign(machine + '|' + expiry + '|' + status)
  };
}

// -------------------------------------------------------------------------
// Admin: generate / revoke / list
// -------------------------------------------------------------------------

function generateCode(p) {
  var planDays = Number(p.plan_days || p.days || 0);
  if (!planDays || planDays < 1) return {ok: false, reason: 'bad_plan_days'};
  var uid = String(p.uid || '');
  var note = String(p.note || '');
  var preMachine = String(p.machine_id || '');   // optional pre-lock to a PC
  var code = newCode();
  var sh = sheet();
  var expiry = '';
  var activated = '';
  var status = 'UNUSED';
  if (preMachine) {   // pre-locked: bind now, start the clock now
    activated = fmt(new Date());
    expiry = fmt(addDays(new Date(), planDays));
    status = 'ACTIVE';
  }
  sh.appendRow([code, planDays, preMachine, uid, fmt(new Date()),
                activated, expiry, status, note]);
  return {ok: true, code: code, plan_days: planDays, uid: uid,
          expiry: expiry, status: status};
}

function revokeCode(p)  { return setStatus(String(p.code || ''), 'REVOKED'); }

function setStatus(code, status) {
  code = String(code || '').trim().toUpperCase();
  var sh = sheet();
  var row = findRow(sh, code);
  if (row < 0) return {ok: false, reason: 'invalid_code'};
  sh.getRange(row, COL.STATUS).setValue(status);
  return {ok: true, code: code, status: status};
}

function resetMachine(code) {   // unbind so it can activate on a new PC
  code = String(code || '').trim().toUpperCase();
  var sh = sheet();
  var row = findRow(sh, code);
  if (row < 0) return {ok: false, reason: 'invalid_code'};
  sh.getRange(row, COL.MACHINE).setValue('');
  sh.getRange(row, COL.ACTIVATED).setValue('');
  sh.getRange(row, COL.EXPIRY).setValue('');
  sh.getRange(row, COL.STATUS).setValue('UNUSED');
  return {ok: true, code: code, status: 'UNUSED'};
}

function listLicenses() {
  var sh = sheet();
  var last = sh.getLastRow();
  var rows = [];
  if (last >= 2) {
    var vals = sh.getRange(2, 1, last - 1, COL.NOTE).getValues();
    for (var i = 0; i < vals.length; i++) {
      var v = vals[i];
      if (!v[COL.CODE - 1]) continue;
      rows.push({
        code: v[COL.CODE - 1], plan_days: v[COL.PLAN - 1],
        machine_id: v[COL.MACHINE - 1], uid: v[COL.UID - 1],
        issued: fmtCell(v[COL.ISSUED - 1]),
        activated: fmtCell(v[COL.ACTIVATED - 1]),
        expiry: fmtCell(v[COL.EXPIRY - 1]),
        status: v[COL.STATUS - 1], note: v[COL.NOTE - 1]
      });
    }
  }
  return {ok: true, count: rows.length, licenses: rows};
}

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function sheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) sh = ss.insertSheet(SHEET_NAME);
  return sh;
}

function findRow(sh, code) {
  var last = sh.getLastRow();
  if (last < 2) return -1;
  var codes = sh.getRange(2, COL.CODE, last - 1, 1).getValues();
  for (var i = 0; i < codes.length; i++) {
    if (String(codes[i][0]).trim().toUpperCase() === code) return i + 2;
  }
  return -1;
}

function newCode() {
  var chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';   // no confusing 0/O/1/I
  var parts = [];
  for (var g = 0; g < 3; g++) {
    var s = '';
    for (var k = 0; k < 4; k++) {
      s += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    parts.push(s);
  }
  return 'TRAV-' + parts.join('-');
}

function sign(message) {
  var raw = Utilities.computeHmacSha256Signature(message, LICENSE_SECRET);
  return Utilities.base64EncodeWebSafe(raw).replace(/=+$/, '');
}

var TZ = Session.getScriptTimeZone();
function today()          { return Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd'); }
function fmt(d)           { return Utilities.formatDate(d, TZ, 'yyyy-MM-dd'); }
function addDays(d, n)    { var x = new Date(d.getTime()); x.setDate(x.getDate() + n); return x; }
function fmtCell(v)       { return (v instanceof Date) ? fmt(v) : String(v || ''); }
function normalizeDate(s) {
  if (s instanceof Date) return fmt(s);
  s = String(s || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : (s ? fmt(new Date(s)) : '');
}

// -------------------------------------------------------------------------
// One-time setup + Sheet menu
// -------------------------------------------------------------------------

function setupSheet() {
  var sh = sheet();
  sh.clear();
  sh.getRange(1, 1, 1, COL.NOTE).setValues([[
    'Code', 'PlanDays', 'MachineID', 'UID', 'IssuedAt',
    'ActivatedAt', 'ExpiryAt', 'Status', 'Note']]);
  sh.getRange(1, 1, 1, COL.NOTE).setFontWeight('bold')
    .setBackground('#d64336').setFontColor('#ffffff');
  sh.setFrozenRows(1);
  sh.autoResizeColumns(1, COL.NOTE);
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🔑 TRAVKOD License')
    .addItem('Generate / Manage Codes', 'openSidebar')
    .addItem('Setup Sheet (headers)', 'setupSheet')
    .addToUi();
}

function openSidebar() {
  var html = HtmlService.createHtmlOutputFromFile('Sidebar')
      .setTitle('TRAVKOD License Admin');
  SpreadsheetApp.getUi().showSidebar(html);
}

// Called by the sidebar (google.script.run) — no ADMIN_KEY needed because
// only the sheet owner can run it.
function uiGenerate(planDays, uid, note, preMachine) {
  return generateCode({plan_days: planDays, uid: uid, note: note,
                       machine_id: preMachine || ''});
}
function uiRevoke(code)  { return revokeCode({code: code}); }
function uiUnrevoke(code){ return setStatus(code, 'ACTIVE'); }
function uiResetPc(code) { return resetMachine(code); }
function uiList()        { return listLicenses(); }
