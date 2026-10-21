import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart' show kReleaseMode;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

/// Adresse du backend Django.
/// - Version publiée (flutter build apk/appbundle) : le site en ligne, en HTTPS.
/// - Développement : le PC hôte vu depuis l'émulateur Android (http://10.0.2.2:8000).
/// Surcharge possible : --dart-define=API_BASE=http://IP_DU_PC:8000 (téléphone réel en local).
const String apiBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: kReleaseMode ? 'https://domiora-5pfq.onrender.com' : 'http://10.0.2.2:8000',
);

class ApiException implements Exception {
  final String message;
  final int? status;
  ApiException(this.message, {this.status});
  bool get isAuth => status == 401 || status == 403;
  @override
  String toString() => message;
}

/// Client unique de l'API DOMIORA. Les règles métier restent côté serveur :
/// l'application n'affiche que ce que l'API autorise.
class Api {
  Api._();
  static final Api instance = Api._();

  static const _storage = FlutterSecureStorage();
  static const _tokenKey = 'domiora_token';
  String? _token;
  final _client = http.Client();

  bool get isLoggedIn => _token != null;

  Future<void> loadToken() async => _token = await _storage.read(key: _tokenKey);

  Future<void> logout() async {
    _token = null;
    await _storage.delete(key: _tokenKey);
  }

  Uri _uri(String path, [Map<String, String>? query]) {
    final full = path.startsWith('http') ? path : '$apiBase$path';
    final uri = Uri.parse(full);
    return query == null ? uri : uri.replace(queryParameters: {...uri.queryParameters, ...query});
  }

  Map<String, String> get _headers => {
        'Accept': 'application/json',
        if (_token != null) 'Authorization': 'Token $_token',
      };

  Future<dynamic> _send(Future<http.Response> Function() call) async {
    http.Response resp;
    try {
      resp = await call().timeout(const Duration(seconds: 15));
    } on TimeoutException {
      throw ApiException('Le serveur ne répond pas. Vérifiez votre connexion.');
    } on SocketException {
      throw ApiException('Pas de connexion au serveur DOMIORA.');
    } on http.ClientException {
      throw ApiException('Erreur réseau. Réessayez.');
    }
    final body = resp.body.isEmpty ? null : jsonDecode(utf8.decode(resp.bodyBytes));
    if (resp.statusCode >= 200 && resp.statusCode < 300) return body;
    if (resp.statusCode == 401 || resp.statusCode == 403) {
      if (_token != null && resp.statusCode == 401) await logout();
      throw ApiException(_detail(body) ?? 'Session expirée ou accès refusé.', status: resp.statusCode);
    }
    throw ApiException(_detail(body) ?? 'Erreur du serveur (${resp.statusCode}).', status: resp.statusCode);
  }

  String? _detail(dynamic body) {
    if (body is Map) {
      for (final k in ['detail', 'error', 'non_field_errors']) {
        final v = body[k];
        if (v is String) return v;
        if (v is List && v.isNotEmpty) return v.first.toString();
      }
    }
    return null;
  }

  Future<dynamic> get(String path, [Map<String, String>? query]) =>
      _send(() => _client.get(_uri(path, query), headers: _headers));

  Future<dynamic> post(String path, Map<String, dynamic> data) => _send(() => _client.post(_uri(path),
      headers: {..._headers, 'Content-Type': 'application/json'}, body: jsonEncode(data)));

  Future<dynamic> delete(String path) => _send(() => _client.delete(_uri(path), headers: _headers));

  Future<void> login(String username, String password) async {
    dynamic data;
    try {
      data = await post('/api/auth/token/', {'username': username, 'password': password});
    } on ApiException catch (e) {
      // 400 = identifiants refusés ; les erreurs réseau gardent leur propre message.
      if (e.status == 400) throw ApiException('Identifiant ou mot de passe incorrect.', status: 400);
      rethrow;
    }
    _token = data['token'] as String;
    await _storage.write(key: _tokenKey, value: _token);
  }
}
