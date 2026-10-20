import 'package:flutter/material.dart';

import '../api.dart';
import '../widgets.dart';

class AccountScreen extends StatefulWidget {
  final VoidCallback onAuthChanged;
  const AccountScreen({super.key, required this.onAuthChanged});
  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  final _user = TextEditingController();
  final _pass = TextEditingController();
  final _form = GlobalKey<FormState>();
  bool _busy = false;
  String? _error;
  Map<String, dynamic>? _me;
  Map<String, dynamic>? _subscription;

  @override
  void initState() {
    super.initState();
    if (Api.instance.isLoggedIn) _loadMe();
  }

  @override
  void dispose() {
    _user.dispose();
    _pass.dispose();
    super.dispose();
  }

  Future<void> _loadMe() async {
    try {
      final me = await Api.instance.get('/api/me/') as Map<String, dynamic>;
      Map<String, dynamic>? sub;
      if (me['role'] == 'owner') {
        try {
          sub = await Api.instance.get('/api/subscriptions/me/') as Map<String, dynamic>;
        } on ApiException {
          sub = null;
        }
      }
      setState(() {
        _me = me;
        _subscription = sub;
        _error = null;
      });
    } on ApiException catch (e) {
      if (e.isAuth) {
        await Api.instance.logout();
        widget.onAuthChanged();
      }
      setState(() => _error = e.isAuth ? 'Session expirée : reconnectez-vous.' : e.message);
    }
  }

  Future<void> _login() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await Api.instance.login(_user.text.trim(), _pass.text);
      _pass.clear();
      await _loadMe();
      widget.onAuthChanged();
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _logout() async {
    await Api.instance.logout();
    setState(() {
      _me = null;
      _subscription = null;
    });
    widget.onAuthChanged();
  }

  @override
  Widget build(BuildContext context) {
    if (!Api.instance.isLoggedIn || _me == null) return _loginForm();
    final me = _me!;
    final role = me['role'] as String? ?? '';
    final name = '${me['first_name'] ?? ''} ${me['last_name'] ?? ''}'.trim();
    return RefreshIndicator(
      onRefresh: _loadMe,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        ListTile(
          leading: const CircleAvatar(child: Icon(Icons.person)),
          title: Text(name.isEmpty ? me['username'] ?? '' : name, style: const TextStyle(fontWeight: FontWeight.bold)),
          subtitle: Text(const {'client': 'Client', 'owner': 'Propriétaire / agent', 'admin': 'Administrateur', 'verifier': 'Vérificateur'}[role] ?? role),
        ),
        const Divider(),
        if (role == 'owner') ...[
          _subscriptionCard(),
          _webTile(Icons.dashboard_outlined, 'Gérer mes annonces', '/dashboard/proprietaire/'),
          _webTile(Icons.question_answer_outlined, 'Questions reçues', '/dashboard/proprietaire/questions/'),
          _webTile(Icons.chat_outlined, 'Messagerie', '/dashboard/proprietaire/messagerie/'),
          _webTile(Icons.workspace_premium_outlined, 'Abonnement', '/dashboard/proprietaire/abonnement/'),
        ],
        if (role == 'client') ...[
          _webTile(Icons.handshake_outlined, 'Mes mises en relation', '/dashboard/client/mes-mises-en-relation/'),
          _webTile(Icons.chat_outlined, 'Messagerie', '/dashboard/client/messagerie/'),
          _webTile(Icons.question_answer_outlined, 'Mes questions', '/dashboard/client/questions/'),
        ],
        if (role == 'verifier') _webTile(Icons.fact_check_outlined, 'Mes missions', '/dashboard/verificateur/'),
        const SizedBox(height: 8),
        const Text('Ces espaces s’ouvrent sur le site DOMIORA (connexion web requise).',
            style: TextStyle(fontSize: 12, color: Colors.black54)),
        const SizedBox(height: 24),
        OutlinedButton.icon(onPressed: _logout, icon: const Icon(Icons.logout), label: const Text('Se déconnecter')),
      ]),
    );
  }

  Widget _subscriptionCard() {
    final s = _subscription;
    if (s == null || s['enabled'] != true) return const SizedBox();
    final end = s['current_period_end'] as String?;
    final endDate = end == null ? null : DateTime.tryParse(end)?.toLocal();
    return Card(
      child: ListTile(
        leading: const Icon(Icons.workspace_premium),
        title: Text('Plan : ${s['plan'] ?? 'gratuit'}'),
        subtitle: Text([
          'Statut : ${s['status'] ?? '-'}',
          if (endDate != null) 'Échéance : ${endDate.day.toString().padLeft(2, '0')}/${endDate.month.toString().padLeft(2, '0')}/${endDate.year}',
          if (s['cancel_at_period_end'] == true) 'Renouvellement désactivé',
          if (s['scheduled_plan'] != null) 'Prochain plan : ${s['scheduled_plan']}',
        ].join('\n')),
      ),
    );
  }

  Widget _webTile(IconData icon, String label, String path) => ListTile(
        leading: Icon(icon),
        title: Text(label),
        trailing: const Icon(Icons.open_in_new, size: 18),
        onTap: () => openWeb(context, '$apiBase$path'),
      );

  Widget _loginForm() => ListView(padding: const EdgeInsets.all(24), children: [
        const SizedBox(height: 24),
        Text('DOMIORA', textAlign: TextAlign.center,
            style: TextStyle(fontSize: 32, fontWeight: FontWeight.w900, color: Theme.of(context).colorScheme.primary)),
        const Text('Immobilier de confiance', textAlign: TextAlign.center),
        const SizedBox(height: 32),
        Form(
          key: _form,
          child: Column(children: [
            TextFormField(
              controller: _user,
              autofillHints: const [AutofillHints.username],
              decoration: const InputDecoration(labelText: "Nom d'utilisateur", border: OutlineInputBorder()),
              validator: (v) => (v == null || v.trim().isEmpty) ? 'Champ obligatoire' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _pass,
              obscureText: true,
              autofillHints: const [AutofillHints.password],
              decoration: const InputDecoration(labelText: 'Mot de passe', border: OutlineInputBorder()),
              validator: (v) => (v == null || v.isEmpty) ? 'Champ obligatoire' : null,
              onFieldSubmitted: (_) => _login(),
            ),
          ]),
        ),
        if (_error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_error!, style: const TextStyle(color: Colors.red))),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: _busy ? null : _login,
          child: _busy ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Se connecter'),
        ),
        const SizedBox(height: 12),
        TextButton(onPressed: () => openWeb(context, '$apiBase/compte/publier-un-bien/'), child: const Text('Créer un compte propriétaire')),
        const Text('Un compte client est créé lors de la première mise en relation depuis une annonce.',
            textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: Colors.black54)),
      ]);
}
