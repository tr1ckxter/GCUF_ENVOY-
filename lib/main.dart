import 'package:flutter/material.dart';
import 'package:flutter/services.dart'; // Added for status bar control
import 'screens/chat_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Set professional status bar colors
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Color(0xFF040084),
      statusBarIconBrightness: Brightness.light,
    ),
  );

  runApp(const GCUFEnvoy());
}

class GCUFEnvoy extends StatelessWidget {
  const GCUFEnvoy({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GCUF Envoy',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF040084),
          primary: const Color(0xFF040084),
          secondary: const Color(0xFFFF8200), // GCUF Orange
        ),
        textTheme: const TextTheme(
          headlineMedium: TextStyle(
            fontWeight: FontWeight.bold,
            color: Color(0xFF040084),
          ),
        ),
      ),
      home: ChatScreen(), // Removed 'const' to allow for dynamic state updates
    );
  }
}
