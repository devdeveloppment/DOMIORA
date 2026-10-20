import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../widgets.dart';
import 'detail.dart';

class FavoritesScreen extends StatefulWidget {
  const FavoritesScreen({super.key});
  @override
  State<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends State<FavoritesScreen> {
  List<Property>? _items;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!Api.instance.isLoggedIn) return;
    setState(() => _error = null);
    try {
      final data = await Api.instance.get('/api/favorites/');
      setState(() => _items = [
            for (final f in data['results'] as List)
              if (f['property_detail'] is Map) Property.fromJson(f['property_detail'] as Map<String, dynamic>)
          ]);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!Api.instance.isLoggedIn) {
      return const EmptyView(message: 'Connectez-vous depuis l’onglet Compte pour retrouver vos favoris.', icon: Icons.favorite_border);
    }
    if (_error != null) return ErrorView(message: _error!, onRetry: _load);
    if (_items == null) return const Center(child: CircularProgressIndicator());
    if (_items!.isEmpty) return const EmptyView(message: 'Aucun favori pour le moment.', icon: Icons.favorite_border);
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(children: [
        for (final p in _items!)
          PropertyCard(
            property: p,
            onTap: () async {
              await Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailScreen(slug: p.slug)));
              _load();
            },
          ),
      ]),
    );
  }
}
