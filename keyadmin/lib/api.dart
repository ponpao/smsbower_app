// TRAVKOD CODEs — Keyadmin API client.
// Talks to the same Google Apps Script Web App as the Visualizer license
// gate. Admin actions send the ADMIN_KEY.

import 'dart:convert';
import 'package:http/http.dart' as http;

class License {
  final String code, machineId, uid, issued, activated, expiry, status, note;
  final int planDays;
  License({
    required this.code,
    required this.planDays,
    required this.machineId,
    required this.uid,
    required this.issued,
    required this.activated,
    required this.expiry,
    required this.status,
    required this.note,
  });

  factory License.fromJson(Map<String, dynamic> j) => License(
        code: '${j['code'] ?? ''}',
        planDays: (j['plan_days'] is int)
            ? j['plan_days']
            : int.tryParse('${j['plan_days']}') ?? 0,
        machineId: '${j['machine_id'] ?? ''}',
        uid: '${j['uid'] ?? ''}',
        issued: '${j['issued'] ?? ''}',
        activated: '${j['activated'] ?? ''}',
        expiry: '${j['expiry'] ?? ''}',
        status: '${j['status'] ?? ''}',
        note: '${j['note'] ?? ''}',
      );

  int? get daysLeft {
    if (expiry.isEmpty) return null;
    final e = DateTime.tryParse(expiry);
    if (e == null) return null;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    return e.difference(today).inDays;
  }
}

class LicenseApi {
  String baseUrl;
  String adminKey;
  LicenseApi(this.baseUrl, this.adminKey);

  Future<Map<String, dynamic>> _get(Map<String, String> params) async {
    final uri = Uri.parse(baseUrl).replace(queryParameters: {
      ...params,
      'admin_key': adminKey,
    });
    final r = await http.get(uri).timeout(const Duration(seconds: 20));
    // Apps Script may 302 to a googleusercontent URL; http follows it.
    return json.decode(r.body) as Map<String, dynamic>;
  }

  Future<bool> ping() async {
    try {
      final r = await _get({'action': 'ping'});
      return r['ok'] == true;
    } catch (_) {
      return false;
    }
  }

  Future<List<License>> list() async {
    final r = await _get({'action': 'list'});
    if (r['ok'] != true) throw Exception(r['reason'] ?? 'error');
    final items = (r['licenses'] as List? ?? []);
    return items
        .map((e) => License.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<String> generate({
    required int days,
    String uid = '',
    String note = '',
    String preMachine = '',
  }) async {
    final r = await _get({
      'action': 'generate',
      'plan_days': '$days',
      'uid': uid,
      'note': note,
      'machine_id': preMachine,
    });
    if (r['ok'] != true) throw Exception(r['reason'] ?? 'error');
    return '${r['code']}';
  }

  Future<void> revoke(String code) => _admin('revoke', code);
  Future<void> unrevoke(String code) => _admin('unrevoke', code);
  Future<void> resetPc(String code) => _admin('reset_pc', code);

  Future<void> _admin(String action, String code) async {
    final r = await _get({'action': action, 'code': code});
    if (r['ok'] != true) throw Exception(r['reason'] ?? 'error');
  }
}
