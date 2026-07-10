// TRAVKOD CODEs — Keyadmin (Flutter). Admin app to generate / revoke
// Visualizer licenses via the Google Apps Script backend.
//
// Build a Universal APK:
//   flutter pub get
//   flutter build apk --release
//   (output: build/app/outputs/flutter-apk/app-release.apk)

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api.dart';

const kAccent = Color(0xFFD64336);
const kAccent2 = Color(0xFFB8352B);

void main() => runApp(const KeyadminApp());

class KeyadminApp extends StatelessWidget {
  const KeyadminApp({super.key});
  @override
  Widget build(BuildContext context) {
    final base = ThemeData(
      useMaterial3: true,
      colorSchemeSeed: kAccent,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF0F1216),
    );
    return MaterialApp(
      title: 'Keyadmin — Visualizer',
      debugShowCheckedModeBanner: false,
      theme: base,
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  LicenseApi? _api;
  List<License> _items = [];
  bool _loading = false;
  String _search = '';

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    final p = await SharedPreferences.getInstance();
    final url = p.getString('url') ?? '';
    final key = p.getString('key') ?? '';
    if (url.isEmpty || key.isEmpty) {
      WidgetsBinding.instance
          .addPostFrameCallback((_) => _openSettings(first: true));
    } else {
      _api = LicenseApi(url, key);
      _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_api == null) return;
    setState(() => _loading = true);
    try {
      final items = await _api!.list();
      items.sort((a, b) => b.issued.compareTo(a.issued));
      setState(() => _items = items);
    } catch (e) {
      _toast('Load failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  void _toast(String m) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(m)));
  }

  Future<void> _openSettings({bool first = false}) async {
    final p = await SharedPreferences.getInstance();
    final urlCtl = TextEditingController(text: p.getString('url') ?? '');
    final keyCtl = TextEditingController(text: p.getString('key') ?? '');
    final ok = await showDialog<bool>(
      context: context,
      barrierDismissible: !first,
      builder: (_) => AlertDialog(
        title: const Text('Server settings'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(
            controller: urlCtl,
            decoration: const InputDecoration(
                labelText: 'Apps Script Web App URL (/exec)'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: keyCtl,
            decoration: const InputDecoration(labelText: 'Admin Key'),
          ),
        ]),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Save')),
        ],
      ),
    );
    if (ok == true) {
      await p.setString('url', urlCtl.text.trim());
      await p.setString('key', keyCtl.text.trim());
      _api = LicenseApi(urlCtl.text.trim(), keyCtl.text.trim());
      _refresh();
    }
  }

  List<License> get _filtered {
    if (_search.isEmpty) return _items;
    final q = _search.toLowerCase();
    return _items
        .where((x) =>
            x.code.toLowerCase().contains(q) ||
            x.owner.toLowerCase().contains(q))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 12,
        title: Row(children: const [
          Icon(Icons.vpn_key_rounded, color: kAccent),
          SizedBox(width: 8),
          Text('Keyadmin', style: TextStyle(fontWeight: FontWeight.bold)),
        ]),
        actions: [
          IconButton(
              onPressed: _refresh, icon: const Icon(Icons.refresh)),
          IconButton(
              onPressed: () => _openSettings(),
              icon: const Icon(Icons.settings)),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: kAccent,
        onPressed: _generateDialog,
        icon: const Icon(Icons.bolt),
        label: const Text('Generate'),
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
          child: TextField(
            onChanged: (v) => setState(() => _search = v),
            decoration: InputDecoration(
              hintText: 'Search code / user / note',
              prefixIcon: const Icon(Icons.search),
              isDense: true,
              filled: true,
              border:
                  OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
        ),
        if (_loading) const LinearProgressIndicator(color: kAccent),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _refresh,
            child: _filtered.isEmpty
                ? ListView(children: const [
                    SizedBox(height: 120),
                    Center(child: Text('No licenses yet — tap Generate.')),
                  ])
                : ListView.builder(
                    itemCount: _filtered.length,
                    itemBuilder: (_, i) => _tile(_filtered[i]),
                  ),
          ),
        ),
      ]),
    );
  }

  Widget _tile(License l) {
    final color = {
      'ACTIVE': Colors.green,
      'REVOKED': Colors.red,
      'EXPIRED': Colors.orange,
      'UNUSED': Colors.blueGrey,
    }[l.status] ?? Colors.grey;
    final dl = l.daysLeft;
    final sub = [
      if (l.owner.isNotEmpty) '👤 ${l.owner}',
      '${l.planDays}d',
      if (l.expiry.isNotEmpty) 'exp ${l.expiry}',
      if (dl != null && l.status == 'ACTIVE') '($dl left)',
    ].join('  ·  ');
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      child: ListTile(
        title: Text(l.code,
            style: const TextStyle(
                fontWeight: FontWeight.bold, letterSpacing: 0.5)),
        subtitle: Text(sub),
        leading: CircleAvatar(
            backgroundColor: color.withOpacity(0.18),
            child: Icon(Icons.circle, size: 12, color: color)),
        trailing: PopupMenuButton<String>(
          onSelected: (v) => _action(v, l),
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'copy', child: Text('Copy code')),
            if (l.status != 'REVOKED')
              const PopupMenuItem(value: 'revoke', child: Text('Revoke')),
            if (l.status == 'REVOKED')
              const PopupMenuItem(value: 'unrevoke', child: Text('Un-revoke')),
            const PopupMenuItem(value: 'reset', child: Text('Reset PC lock')),
          ],
        ),
        onTap: () => _action('copy', l),
      ),
    );
  }

  Future<void> _action(String v, License l) async {
    if (_api == null) return;
    try {
      switch (v) {
        case 'copy':
          await Clipboard.setData(ClipboardData(text: l.code));
          _toast('Copied ${l.code}');
          return;
        case 'revoke':
          await _api!.revoke(l.code);
          _toast('Revoked ${l.code}');
          break;
        case 'unrevoke':
          await _api!.unrevoke(l.code);
          _toast('Un-revoked ${l.code}');
          break;
        case 'reset':
          await _api!.resetPc(l.code);
          _toast('PC lock reset for ${l.code}');
          break;
      }
      _refresh();
    } catch (e) {
      _toast('Failed: $e');
    }
  }

  Future<void> _generateDialog() async {
    if (_api == null) {
      _openSettings(first: true);
      return;
    }
    int days = 30;
    final ownerCtl = TextEditingController();
    final customCtl = TextEditingController();
    final presets = {'1 Day': 1, '7 Days': 7, '1 Month': 30, '3 Months': 90, '1 Year': 365};

    final created = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(builder: (ctx, setSheet) {
        return Padding(
          padding: EdgeInsets.only(
            left: 16, right: 16, top: 16,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 16,
          ),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Generate License',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Wrap(spacing: 8, children: [
              for (final e in presets.entries)
                ChoiceChip(
                  label: Text(e.key),
                  selected: days == e.value && customCtl.text.isEmpty,
                  selectedColor: kAccent,
                  onSelected: (_) => setSheet(() {
                    days = e.value;
                    customCtl.clear();
                  }),
                ),
            ]),
            const SizedBox(height: 8),
            TextField(
              controller: customCtl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                  labelText: 'Custom days (optional)'),
              onChanged: (v) => setSheet(() => days = int.tryParse(v) ?? days),
            ),
            TextField(
                controller: ownerCtl,
                decoration: const InputDecoration(
                    labelText: 'Owner / User name (ឈ្មោះអ្នកប្រើ)')),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: kAccent),
                icon: const Icon(Icons.bolt),
                label: Text('Generate  ·  $days days'),
                onPressed: () async {
                  try {
                    final code = await _api!.generate(
                        days: days,
                        owner: ownerCtl.text.trim());
                    if (ctx.mounted) Navigator.pop(ctx, code);
                  } catch (e) {
                    _toast('Failed: $e');
                  }
                },
              ),
            ),
          ]),
        );
      }),
    );

    if (created != null) {
      await _refresh();
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Code created ✅'),
          content: SelectableText(created,
              style: const TextStyle(
                  fontSize: 22, fontWeight: FontWeight.bold, letterSpacing: 1)),
          actions: [
            TextButton(
              onPressed: () {
                Clipboard.setData(ClipboardData(text: created));
                Navigator.pop(context);
                _toast('Copied — send it to the user');
              },
              child: const Text('Copy'),
            ),
          ],
        ),
      );
    }
  }
}
