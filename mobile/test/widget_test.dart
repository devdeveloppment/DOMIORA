import 'package:domiora_mobile/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Property.fromJson utilise le prix formaté par le serveur et les images', () {
    final p = Property.fromJson({
      'id': 1, 'slug': 'villa', 'title': 'Villa', 'price': '250000.00', 'price_display': '250 000 FCFA/mois',
      'city': 'Lomé', 'bedrooms': 3, 'bathrooms': 2, 'surface_area': '180.00', 'badge_label': 'À LOUER',
      'owner': {'first_name': 'Kossi'}, 'web_url': 'http://x/proprietes/villa/',
      'images': [{'image': 'http://x/a.webp'}, {'image': 'http://x/b.webp'}],
    });
    expect(p.priceDisplay, '250 000 FCFA/mois');
    expect(p.cover, 'http://x/a.webp');
    expect(p.images.length, 2);
    expect(p.ownerName, 'Kossi');
  });

  test('Property.fromJson tolère les champs absents', () {
    final p = Property.fromJson({'id': 2, 'price': '1000', 'images': [], 'primary_image': 'http://x/c.jpg'});
    expect(p.priceDisplay, '1000 FCFA');
    expect(p.cover, 'http://x/c.jpg');
    expect(p.bedrooms, 0);
  });

  test('AppNotification.fromJson', () {
    final n = AppNotification.fromJson({'id': 3, 'title': 'T', 'message': 'M', 'is_read': false, 'created_at': '2026-10-19T10:00:00Z'});
    expect(n.isRead, false);
    expect(n.createdAt.toUtc().hour, 10);
  });
}
