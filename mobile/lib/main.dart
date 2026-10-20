import 'package:flutter/material.dart';

import 'api.dart';
import 'screens/account.dart';
import 'screens/favorites.dart';
import 'screens/home.dart';
import 'screens/notifications.dart';

const brand = Color(0xFF5A1A24);
const gold = Color(0xFFB8860B);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Api.instance.loadToken();
  runApp(const DomioraApp());
}

class DomioraApp extends StatelessWidget {
  const DomioraApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DOMIORA',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: brand, primary: brand, secondary: gold),
        useMaterial3: true,
      ),
      home: const Shell(),
    );
  }
}

class Shell extends StatefulWidget {
  const Shell({super.key});
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _index = 0;

  void _refresh() => setState(() {});

  @override
  Widget build(BuildContext context) {
    final pages = [
      const HomeScreen(),
      FavoritesScreen(key: ValueKey('fav${Api.instance.isLoggedIn}')),
      NotificationsScreen(key: ValueKey('notif${Api.instance.isLoggedIn}')),
      AccountScreen(onAuthChanged: _refresh),
    ];
    return Scaffold(
      body: SafeArea(child: IndexedStack(index: _index, children: pages)),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Annonces'),
          NavigationDestination(icon: Icon(Icons.favorite_border), selectedIcon: Icon(Icons.favorite), label: 'Favoris'),
          NavigationDestination(icon: Icon(Icons.notifications_none), selectedIcon: Icon(Icons.notifications), label: 'Alertes'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Compte'),
        ],
      ),
    );
  }
}
