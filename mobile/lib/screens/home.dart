import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../widgets.dart';
import 'detail.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _items = <Property>[];
  final _search = TextEditingController();
  final _scroll = ScrollController();
  String? _next;
  String? _error;
  bool _loading = false;
  String _type = '';
  String _transaction = '';
  Map<String, String> _types = {'': 'Tous types'};
  Map<String, String> _transactions = {'': 'Tout'};

  @override
  void initState() {
    super.initState();
    _loadConfig();
    _load(reset: true);
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 400) _load();
    });
  }

  @override
  void dispose() {
    _search.dispose();
    _scroll.dispose();
    super.dispose();
  }

  /// Types de biens et de transaction fournis par le serveur (aucune liste figée dans l'app).
  Future<void> _loadConfig() async {
    try {
      final cfg = await Api.instance.get('/api/app-config/');
      setState(() {
        _types = {'': 'Tous types', for (final t in cfg['property_types']) t['value'] as String: t['label'] as String};
        _transactions = {'': 'Tout', for (final t in cfg['transaction_types']) t['value'] as String: t['label'] as String};
      });
    } on ApiException {
      // Les filtres restent disponibles sous leur forme minimale ; la liste se charge quand même.
    }
  }

  Future<void> _load({bool reset = false}) async {
    if (_loading || (!reset && _next == null)) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = reset
          ? await Api.instance.get('/api/properties/', {
              if (_search.text.trim().isNotEmpty) 'search': _search.text.trim(),
              if (_type.isNotEmpty) 'property_type': _type,
              if (_transaction.isNotEmpty) 'transaction_type': _transaction,
            })
          : await Api.instance.get(_next!);
      final results = (data['results'] as List).map((e) => Property.fromJson(e as Map<String, dynamic>)).toList();
      setState(() {
        if (reset) _items.clear();
        _items.addAll(results);
        _next = data['next'] as String?;
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
        child: TextField(
          controller: _search,
          textInputAction: TextInputAction.search,
          onSubmitted: (_) => _load(reset: true),
          decoration: InputDecoration(
            hintText: 'Ville, quartier, type de bien…',
            prefixIcon: const Icon(Icons.search),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
            isDense: true,
          ),
        ),
      ),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Row(children: [
          for (final t in _transactions.entries)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text(t.value),
                selected: _transaction == t.key,
                onSelected: (_) {
                  setState(() => _transaction = t.key);
                  _load(reset: true);
                },
              ),
            ),
          DropdownButton<String>(
            value: _type,
            underline: const SizedBox(),
            items: [for (final e in _types.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
            onChanged: (v) {
              setState(() => _type = v ?? '');
              _load(reset: true);
            },
          ),
        ]),
      ),
      Expanded(child: _body()),
    ]);
  }

  Widget _body() {
    if (_error != null && _items.isEmpty) return ErrorView(message: _error!, onRetry: () => _load(reset: true));
    if (_items.isEmpty && _loading) return const Center(child: CircularProgressIndicator());
    if (_items.isEmpty) return const EmptyView(message: 'Aucun bien ne correspond à votre recherche.', icon: Icons.search_off);
    return RefreshIndicator(
      onRefresh: () => _load(reset: true),
      child: ListView.builder(
        controller: _scroll,
        itemCount: _items.length + 1,
        itemBuilder: (context, i) {
          if (i == _items.length) {
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Center(child: _loading ? const CircularProgressIndicator() : const SizedBox()),
            );
          }
          final p = _items[i];
          return PropertyCard(
            property: p,
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => DetailScreen(slug: p.slug))),
          );
        },
      ),
    );
  }
}
