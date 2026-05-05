import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  List<Map<String, String>> messages = [];
  bool isLoading = false; // To show the spinner

  Future<void> sendMessage(String query) async {
    setState(() {
      messages.add({"role": "user", "text": query});
      isLoading = true;
    });

    try {
      // 1. Pointing to our local AI bridge
      final url = Uri.parse("http://127.0.0.1:8000/query");

      // 2. The 120-second timeout fix
      final response = await http
          .post(
            url,
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({"query": query}),
          )
          .timeout(const Duration(seconds: 120));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // 3. Matching the 'response' key from main.py
        String aiResponse = data['response'] ?? "I couldn't process that.";

        setState(() {
          messages.add({"role": "bot", "text": aiResponse});
        });
      } else {
        setState(() {
          messages.add({
            "role": "bot",
            "text": "Error: Server returned ${response.statusCode}",
          });
        });
      }
    } catch (e) {
      setState(() {
        messages.add({
          "role": "bot",
          "text": "Connection Error: Is the bridge running? ($e)",
        });
      });
    } finally {
      setState(() {
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          "GCUF Envoy",
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        backgroundColor: const Color.fromARGB(255, 1, 39, 252),
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              itemCount: messages.length,
              itemBuilder: (context, index) {
                bool isUser = messages[index]['role'] == "user";
                return ListTile(
                  title: Align(
                    alignment: isUser
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: Container(
                      padding: EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: isUser
                            ? Colors.deepOrangeAccent
                            : Colors.blue[100],
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(messages[index]['text']!),
                    ),
                  ),
                );
              },
            ),
          ),
          if (isLoading) LinearProgressIndicator(), // Loading bar
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: InputDecoration(hintText: "Ask about GCUF..."),
                  ),
                ),
                IconButton(
                  icon: Icon(Icons.send),
                  onPressed: () {
                    if (_controller.text.isNotEmpty) {
                      sendMessage(_controller.text);
                      _controller.clear();
                    }
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
