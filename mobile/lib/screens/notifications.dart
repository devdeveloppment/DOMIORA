import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../widgets.dart';

/// Notifications par interrogation périodique (30 s) : pas de push tant qu'aucun service
/// (Firebase Cloud Messaging) n'est configuré côté serveur.
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<AppNotification>? _items;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _load(silent: true));
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    if (!Api.instance.isLoggedIn) return;
    if (!silent) setState(() => _error = null);
    try {
      final data = await Api.instance.get('/api/notifications/');
      if (!mounted) return;
      setState(() => _items = [for (final n in data['results'] as List) AppNotification.fromJson(n as Map<String, dynamic>)]);
    } on ApiException catch (e) {
      if (!silent && mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _markRead(AppNotification n) async {
    try {
      await Api.instance.post('/api/notifications/${n.id}/mark_read/', {});
      _load(silent: true);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!Api.instance.isLoggedIn) {
      return const EmptyView(message: 'Connectez-vous pour recevoir vos notifications.', icon: Icons.notifications_none);
    }
    if (_error != null) return ErrorView(message: _error!, onRetry: _load);
    if (_items == null) return const Center(child: CircularProgressIndicator());
    if (_items!.isEmpty) return const EmptyView(message: 'Aucune notification.', icon: Icons.notifications_none);
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        itemCount: _items!.length,
        separatorBuilder: (_, _) => const Divider(height: 1),
        itemBuilder: (_, i) {
          final n = _items![i];
          final d = n.createdAt;
          return ListTile(
            leading: Icon(n.isRead ? Icons.notifications_none : Icons.notifications_active,
                color: n.isRead ? Colors.grey : Theme.of(context).colorScheme.primary),
            title: Text(n.title, style: TextStyle(fontWeight: n.isRead ? FontWeight.normal : FontWeight.bold)),
            subtitle: Text('${n.message}\n${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year} '
                '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}'),
            isThreeLine: true,
            trailing: n.isRead ? null : TextButton(onPressed: () => _markRead(n), child: const Text('Lu')),
          );
        },
      ),
    );
  }
}
