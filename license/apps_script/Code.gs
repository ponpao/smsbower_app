/****************************************************************************
 * TRAVKOD CODEs — License Server (Google Apps Script, bound to a Sheet)
 * ==========================================================================
 * Backs the Video Visualizer license gate AND the Keyadmin Flutter app.
 *
 * Sheet columns (row 1 headers — run setupSheet() to create them):
 *   A License_Key | B Duration | C Device_UID | D Phone_Model | E Status |
 *   F Activation_Date | G Expiry_Date | H Owner
 *
 * SETUP (full walk-through in apps_script/README_SETUP.md):
 *   1. Google Sheet ▸ Extensions ▸ Apps Script ▸ paste this file.
 *   2. Add file "Sidebar.html" (from apps_script/Sidebar.html).
 *   3. Set LICENSE_SECRET (== TRAVKOD_LICENSE_SECRET in license_client.py)
 *      and ADMIN_KEY (a private password for the Keyadmin app).
 *   4. Run setupSheet() once.
 *   5. Deploy ▸ New deployment ▸ Web app ▸ Execute as: Me ▸ Access: Anyone.
 *      Put the /exec URL into WEB_APP_URL (license_client.py) and Keyadmin.
 ***************************************************************************/

// ==== CONFIG — CHANGE THESE ====
var LICENSE_SECRET = 'CHANGE-ME-to-a-long-random-secret-2026'; // == Python
var ADMIN_KEY      = 'CHANGE-ME-admin-password';               // admin only
var SHEET_NAME     = 'Licenses';

// Column order (1-based) — matches the header row.
var COL = {CODE:1, PLAN:2, MACHINE:3, MODEL:4, STATUS:5,
          ACTIVATED:6, EXPIRY:7, OWNER:8};
var NCOL = 8;

// -------------------------------------------------------------------------
// Web entry points
// -------------------------------------------------------------------------

function doPost(e) {
  var out;
  try { out = route(JSON.parse(e.postData.contents || '{}')); }
  catch (err) { out = {ok:false, reason:'server_error', detail:String(err)}; }
  return json(out);
}

function doGet(e) {
  var out;
  try { out = route(e.parameter || {}); }
  catch (err) { out = {ok:false, reason:'server_error', detail:String(err)}; }
  return json(out);
}

function json(o) {
  return ContentService.createTextOutput(JSON.stringify(o))
      .setMimeType(ContentService.MimeType.JSON);
}

function route(p) {
  switch (p.action || '') {
    case 'activate': return clientCheck(p, true);
    case 'validate': return clientCheck(p, false);
    case 'ping':     return {ok:true, server_date: today()};
    case 'generate': return admin(p) || generateCode(p);
    case 'revoke':   return admin(p) || setStatus(p.code, 'REVOKED');
    case 'unrevoke': return admin(p) || setStatus(p.code, 'ACTIVE');
    case 'reset_pc': return admin(p) || resetMachine(p.code);
    case 'list':     return admin(p) || listLicenses();
    default:         return {ok:false, reason:'unknown_action'};
  }
}

function admin(p) {
  if ((p.admin_key || '') !== ADMIN_KEY) return {ok:false, reason:'forbidden'};
  return null;
}

// -------------------------------------------------------------------------
// Client: activate / validate
// -------------------------------------------------------------------------

function clientCheck(p, isActivate) {
  var code = String(p.code || '').trim().toUpperCase();
  var machine = String(p.machine_id || '').trim();
  var model = String(p.device_model || '');
  if (!code || !machine) return {ok:false, reason:'invalid_code'};

  var sh = sheet();
  var row = findRow(sh, code);
  if (row < 0) return {ok:false, reason:'invalid_code'};

  var v = sh.getRange(row, 1, 1, NCOL).getValues()[0];
  var status = String(v[COL.STATUS-1] || 'UNUSED').toUpperCase();
  if (status === 'REVOKED') return {ok:false, reason:'revoked'};

  var boundMachine = String(v[COL.MACHINE-1] || '').trim();
  var planDays = Number(v[COL.PLAN-1] || 0);
  var owner = String(v[COL.OWNER-1] || '');

  if (!boundMachine) {
    if (!isActivate) return {ok:false, reason:'invalid_code'};
    var act = new Date();
    var exp = addDays(act, planDays);
    sh.getRange(row, COL.MACHINE).setValue(machine);
    if (model) sh.getRange(row, COL.MODEL).setValue(model);
    sh.getRange(row, COL.ACTIVATED).setValue(fmt(act));
    sh.getRange(row, COL.EXPIRY).setValue(fmt(exp));
    sh.getRange(row, COL.STATUS).setValue('ACTIVE');
    return reply(machine, fmt(exp), 'ACTIVE', planDays, owner);
  }
  if (boundMachine !== machine) return {ok:false, reason:'code_used_on_another_pc'};

  var expiry = normalizeDate(v[COL.EXPIRY-1]);
  if (!expiry) {
    var a = normalizeDate(v[COL.ACTIVATED-1]) || today();
    expiry = fmt(addDays(new Date(a), planDays));
    sh.getRange(row, COL.EXPIRY).setValue(expiry);
  }
  if (today() > expiry) {
    sh.getRange(row, COL.STATUS).setValue('EXPIRED');
    return {ok:false, reason:'expired', expiry:expiry, owner:owner};
  }
  return reply(machine, expiry, 'ACTIVE', planDays, owner);
}

function reply(machine, expiry, status, planDays, owner) {
  return {
    ok:true, machine_id:machine, expiry:expiry, status:status,
    plan_days:planDays, owner:owner, server_date:today(),
    sig: sign(machine + '|' + expiry + '|' + status)
  };
}

// -------------------------------------------------------------------------
// Admin: generate / revoke / reset / list
// -------------------------------------------------------------------------

function generateCode(p) {
  var planDays = Number(p.plan_days || p.days || 0);
  if (!planDays || planDays < 1) return {ok:false, reason:'bad_plan_days'};
  var owner = String(p.owner || p.uid || '');
  var preMachine = String(p.machine_id || '');   // optional pre-lock
  var code = newCode();
  var expiry = '', activated = '', status = 'UNUSED';
  if (preMachine) {
    activated = fmt(new Date());
    expiry = fmt(addDays(new Date(), planDays));
    status = 'ACTIVE';
  }
  // A License_Key | B Duration | C Device_UID | D Phone_Model | E Status |
  // F Activation_Date | G Expiry_Date | H Owner
  sheet().appendRow([code, planDays, preMachine, '', status,
                     activated, expiry, owner]);
  return {ok:true, code:code, plan_days:planDays, owner:owner,
          expiry:expiry, status:status};
}

function setStatus(code, status) {
  code = String(code || '').trim().toUpperCase();
  var sh = sheet(), row = findRow(sh, code);
  if (row < 0) return {ok:false, reason:'invalid_code'};
  sh.getRange(row, COL.STATUS).setValue(status);
  return {ok:true, code:code, status:status};
}

function resetMachine(code) {
  code = String(code || '').trim().toUpperCase();
  var sh = sheet(), row = findRow(sh, code);
  if (row < 0) return {ok:false, reason:'invalid_code'};
  sh.getRange(row, COL.MACHINE).setValue('');
  sh.getRange(row, COL.MODEL).setValue('');
  sh.getRange(row, COL.ACTIVATED).setValue('');
  sh.getRange(row, COL.EXPIRY).setValue('');
  sh.getRange(row, COL.STATUS).setValue('UNUSED');
  return {ok:true, code:code, status:'UNUSED'};
}

function listLicenses() {
  var sh = sheet(), last = sh.getLastRow(), rows = [];
  if (last >= 2) {
    var vals = sh.getRange(2, 1, last-1, NCOL).getValues();
    for (var i = 0; i < vals.length; i++) {
      var v = vals[i];
      if (!v[COL.CODE-1]) continue;
      rows.push({
        code: v[COL.CODE-1], plan_days: v[COL.PLAN-1],
        machine_id: v[COL.MACHINE-1], phone_model: v[COL.MODEL-1],
        status: v[COL.STATUS-1], activated: fmtCell(v[COL.ACTIVATED-1]),
        expiry: fmtCell(v[COL.EXPIRY-1]), owner: v[COL.OWNER-1]
      });
    }
  }
  return {ok:true, count:rows.length, licenses:rows};
}

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function sheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
}

function findRow(sh, code) {
  var last = sh.getLastRow();
  if (last < 2) return -1;
  var codes = sh.getRange(2, COL.CODE, last-1, 1).getValues();
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
    for (var k = 0; k < 4; k++) s += chars.charAt(Math.floor(Math.random()*chars.length));
    parts.push(s);
  }
  return 'TRAV-' + parts.join('-');
}

function sign(message) {
  var raw = Utilities.computeHmacSha256Signature(message, LICENSE_SECRET);
  return Utilities.base64EncodeWebSafe(raw).replace(/=+$/, '');
}

var TZ = Session.getScriptTimeZone();
function today()       { return Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd'); }
function fmt(d)        { return Utilities.formatDate(d, TZ, 'yyyy-MM-dd'); }
function addDays(d, n) { var x = new Date(d.getTime()); x.setDate(x.getDate()+n); return x; }
function fmtCell(v)    { return (v instanceof Date) ? fmt(v) : String(v || ''); }
function normalizeDate(s) {
  if (s instanceof Date) return fmt(s);
  s = String(s || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : (s ? fmt(new Date(s)) : '');
}

// -------------------------------------------------------------------------
// One-time setup + Sheet menu + sidebar bridge
// -------------------------------------------------------------------------

function setupSheet() {
  var sh = sheet();
  sh.clear();
  sh.getRange(1, 1, 1, NCOL).setValues([[
    'License_Key', 'Duration', 'Device_UID', 'Phone_Model', 'Status',
    'Activation_Date', 'Expiry_Date', 'Owner']]);
  sh.getRange(1, 1, 1, NCOL).setFontWeight('bold')
    .setBackground('#d64336').setFontColor('#ffffff');
  sh.setFrozenRows(1);
  sh.autoResizeColumns(1, NCOL);
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

// Called by the sidebar (google.script.run) — owner is the user's name.
function uiGenerate(planDays, owner, preMachine) {
  return generateCode({plan_days: planDays, owner: owner,
                       machine_id: preMachine || ''});
}
function uiRevoke(code)   { return setStatus(code, 'REVOKED'); }
function uiUnrevoke(code) { return setStatus(code, 'ACTIVE'); }
function uiResetPc(code)  { return resetMachine(code); }
function uiList()         { return listLicenses(); }
