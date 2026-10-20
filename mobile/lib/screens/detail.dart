import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../widgets.dart';

class DetailScreen extends StatefulWidget {
  final String slug;
  const DetailScreen({super.key, required this.slug});
  @override
  State<DetailScreen> createState() => _DetailScreenState();
}

class _DetailScreenState extends State<DetailScreen> {
  Property? _p;
  String? _error;
  int? _fee;
  int? _favoriteId;
  bool _favBusy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final data = await Api.instance.get('/api/properties/${widget.slug}/');
      Map<String, dynamic>? cfg;
      try {
        cfg = await Api.instance.get('/api/app-config/') as Map<String, dynamic>;
      } on ApiException {
        cfg = null; // serveur plus ancien : le tarif s'affichera sur le site
      }
      int? fav;
      if (Api.instance.isLoggedIn) {
        try {
          final favs = await Api.instance.get('/api/favorites/');
          for (final f in favs['results'] as List) {
            if (f['property'] == data['id']) fav = f['id'] as int;
          }
        } on ApiException {
          fav = null;
        }
      }
      setState(() {
        _p = Property.fromJson(data as Map<String, dynamic>);
        _fee = cfg?['contact_fee_amount'] as int?;
        _favoriteId = fav;
      });
    } on ApiException catch (e) {
      setState(() => _error = e.status == 404 ? "Cette annonce n'est plus disponible." : e.message);
    }
  }

  Future<void> _toggleFavorite() async {
    if (!Api.instance.isLoggedIn) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Connectez-vous (onglet Compte) pour gérer vos favoris.')));
      return;
    }
    setState(() => _favBusy = true);
    try {
      if (_favoriteId != null) {
        await Api.instance.delete('/api/favorites/$_favoriteId/');
        setState(() => _favoriteId = null);
      } else {
        final f = await Api.instance.post('/api/favorites/', {'property': _p!.id});
        setState(() => _favoriteId = f['id'] as int);
      }
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _favBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _p;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Annonce'),
        actions: [
          if (p != null)
            IconButton(
              tooltip: _favoriteId != null ? 'Retirer des favoris' : 'Ajouter aux favoris',
              onPressed: _favBusy ? null : _toggleFavorite,
              icon: Icon(_favoriteId != null ? Icons.favorite : Icons.favorite_border),
            ),
        ],
      ),
      body: _error != null
          ? ErrorView(message: _error!, onRetry: _load)
          : p == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(children: [
                  if (p.images.isNotEmpty)
                    SizedBox(
                      height: 240,
                      child: PageView(children: [
                        for (final url in p.images)
                          Image.network(url, fit: BoxFit.cover, cacheWidth: 1000,
                              errorBuilder: (_, _, _) => const Icon(Icons.broken_image)),
                      ]),
                    ),
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(p.priceDisplay,
                          style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: Theme.of(context).colorScheme.primary)),
                      const SizedBox(height: 4),
                      Text(p.title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 4),
                      Text('${p.city} · ${p.badge}', style: const TextStyle(color: Colors.black54)),
                      if (p.verification.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(p.verification, style: const TextStyle(color: Colors.green, fontWeight: FontWeight.w600)),
                        ),
                      const SizedBox(height: 12),
                      Wrap(spacing: 16, runSpacing: 8, children: [
                        if (p.bedrooms > 0) Text('🛏 ${p.bedrooms} chambre(s)'),
                        if (p.bathrooms > 0) Text('🛁 ${p.bathrooms} salle(s) de bain'),
                        if (p.surface.isNotEmpty && p.surface != '0.00') Text('📐 ${p.surface.split('.').first} m²'),
                      ]),
                      const SizedBox(height: 16),
                      Text(p.description),
                      const SizedBox(height: 24),
                      FilledButton.icon(
                        onPressed: p.webUrl.isEmpty ? null : () => openWeb(context, p.webUrl),
                        icon: const Icon(Icons.lock_open),
                        label: Text(_fee == null ? 'Contacter le propriétaire' : 'Contacter le propriétaire ($_fee FCFA)'),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        "La mise en relation, le paiement et la messagerie s'ouvrent sur le site sécurisé DOMIORA. "
                        "Les coordonnées du propriétaire ne sont jamais affichées avant la mise en relation.",
                        style: TextStyle(fontSize: 12, color: Colors.black54),
                      ),
                    ]),
                  ),
                ]),
    );
  }
}
