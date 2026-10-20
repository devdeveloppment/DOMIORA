import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'models.dart';

/// Ouvre une page du site DOMIORA (paiement, messagerie, tableau de bord) dans le navigateur :
/// ces parcours restent gérés et contrôlés par le serveur.
Future<void> openWeb(BuildContext context, String url) async {
  final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  if (!ok && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Impossible d'ouvrir le navigateur.")));
  }
}

class ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const ErrorView({super.key, required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.wifi_off, size: 48, color: Colors.grey),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text('Réessayer')),
          ]),
        ),
      );
}

class EmptyView extends StatelessWidget {
  final String message;
  final IconData icon;
  const EmptyView({super.key, required this.message, this.icon = Icons.inbox_outlined});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 48, color: Colors.grey),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center, style: const TextStyle(color: Colors.black54)),
          ]),
        ),
      );
}

class PropertyCard extends StatelessWidget {
  final Property property;
  final VoidCallback onTap;
  const PropertyCard({super.key, required this.property, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      clipBehavior: Clip.antiAlias,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: InkWell(
        onTap: onTap,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          AspectRatio(
            aspectRatio: 16 / 9,
            child: property.cover == null
                ? Container(color: Colors.black12, child: const Icon(Icons.home_work_outlined, size: 48))
                : Image.network(property.cover!, fit: BoxFit.cover, cacheWidth: 800,
                    errorBuilder: (_, _, _) => Container(color: Colors.black12, child: const Icon(Icons.broken_image))),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(property.priceDisplay, style: TextStyle(color: scheme.primary, fontWeight: FontWeight.w800, fontSize: 18)),
              const SizedBox(height: 2),
              Text(property.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              Wrap(spacing: 8, runSpacing: 4, children: [
                _chip(Icons.place_outlined, property.city),
                if (property.bedrooms > 0) _chip(Icons.bed_outlined, '${property.bedrooms} ch.'),
                if (property.badge.isNotEmpty) _chip(Icons.sell_outlined, property.badge),
              ]),
              if (property.verification.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(property.verification, style: const TextStyle(color: Colors.green, fontSize: 12, fontWeight: FontWeight.w600)),
              ],
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _chip(IconData icon, String label) => Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14, color: Colors.black54),
        const SizedBox(width: 2),
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.black54)),
      ]);
}
