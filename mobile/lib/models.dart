class Property {
  final int id;
  final String slug;
  final String title;
  final String description;
  final String priceDisplay;
  final String city;
  final String propertyType;
  final String transactionType;
  final int bedrooms;
  final int bathrooms;
  final String surface;
  final String badge;
  final String verification;
  final String ownerName;
  final String webUrl;
  final List<String> images;

  Property.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        slug = j['slug'] ?? '',
        title = j['title'] ?? '',
        description = j['description'] ?? '',
        priceDisplay = j['price_display'] ?? '${j['price']} FCFA',
        city = j['city'] ?? '',
        propertyType = j['property_type'] ?? '',
        transactionType = j['transaction_type'] ?? '',
        bedrooms = (j['bedrooms'] ?? 0) as int,
        bathrooms = (j['bathrooms'] ?? 0) as int,
        surface = (j['surface_area'] ?? '').toString(),
        badge = j['badge_label'] ?? '',
        verification = j['owner_verification_label'] ?? '',
        ownerName = (j['owner'] is Map) ? (j['owner']['first_name'] ?? '') : '',
        webUrl = j['web_url'] ?? '',
        images = [
          for (final i in (j['images'] as List? ?? const [])) if (i is Map && i['image'] != null) i['image'] as String,
          if ((j['images'] as List? ?? const []).isEmpty && j['primary_image'] is String) j['primary_image'] as String,
        ];

  String? get cover => images.isEmpty ? null : images.first;
}

class AppNotification {
  final int id;
  final String title;
  final String message;
  final bool isRead;
  final DateTime createdAt;

  AppNotification.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        title = j['title'] ?? '',
        message = j['message'] ?? '',
        isRead = j['is_read'] == true,
        createdAt = DateTime.tryParse(j['created_at'] ?? '')?.toLocal() ?? DateTime.now();
}
