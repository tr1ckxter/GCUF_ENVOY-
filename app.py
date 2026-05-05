import flet as ft
import requests

def main(page: ft.Page):
    page.title = "UNI-AI | Premium Knowledge Core"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0F1115"
    page.window_width = 1000
    page.window_height = 800
    page.padding = 0

    chat_log = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE, spacing=20)

    def create_chat_bubble(text, is_user):
        return ft.Container(
            content=ft.Text(text, size=15, color="white" if is_user else "#E0E0E0"),
            padding=15,
            border_radius=ft.BorderRadius.all(15),
            bgcolor="#1E2229" if is_user else "#1A73E8",
        )

    def send_click(e):
        if not user_input.value: 
            return
        
        user_text = user_input.value
        chat_log.controls.append(
            ft.Row([create_chat_bubble(user_text, True)], alignment=ft.MainAxisAlignment.END)
        )
        user_input.value = ""
        page.update()

        try:
            # --- CONNECTION LOGIC SYNCED WITH MAIN.PY ---
            url = "http://127.0.0.1:8000/query"
            payload = {"query": user_text}
            
            # Increased timeout to 120s to allow Gemma time to process complex PDF data
            res = requests.post(url, json=payload, timeout=120)
            
            # Getting 'response' key as defined in main.py
            answer = res.json().get("response", "System calibration error.")
            
            chat_log.controls.append(
                ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME, color="#1A73E8", size=20),
                    create_chat_bubble(answer, False)
                ], alignment=ft.MainAxisAlignment.START)
            )
        except Exception as ex:
            # Debugging info in your terminal
            print(f"Connection Error: {ex}")
            chat_log.controls.append(
                ft.Row([
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color="red", size=20),
                    ft.Text("SYSTEM OFFLINE: Ensure main.py is running and ADB bridge is active.", 
                            color="red", italic=True)
                ], alignment=ft.MainAxisAlignment.START)
            )
        
        page.update()

    # --- SIDEBAR ---
    sidebar = ft.Container(
        content=ft.Column([
            ft.Text("UNI-AI", size=24, weight="bold", color="white"),
            ft.Text("v1.0 - Premium", size=12, color="#1A73E8"),
            ft.Divider(height=40, color="#2D323B"),
            ft.ListTile(leading=ft.Icon(ft.Icons.DASHBOARD), title=ft.Text("Core Knowledge")),
            ft.ListTile(leading=ft.Icon(ft.Icons.HISTORY), title=ft.Text("Recent Queries"), opacity=0.5),
            ft.ListTile(leading=ft.Icon(ft.Icons.SETTINGS), title=ft.Text("System Config"), opacity=0.5),
            ft.Container(expand=True), 
            ft.Container(
                content=ft.Row([
                    ft.Container(width=10, height=10, bgcolor="green", border_radius=5),
                    ft.Text("Ollama Engine: Active", size=12)
                ]),
                padding=10
            )
        ]),
        width=250,
        bgcolor="#16191E",
        padding=25,
    )

    user_input = ft.TextField(
        hint_text="Query the University Core...",
        border_radius=15,
        bgcolor="#1E2229",
        border_color="#2D323B",
        expand=True,
        on_submit=send_click,
        content_padding=20,
    )

    chat_view = ft.Container(
        content=ft.Column([
            ft.Container(content=chat_log, expand=True, padding=20),
            ft.Container(
                content=ft.Row([
                    user_input, 
                    ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color="#1A73E8", on_click=send_click)
                ]),
                padding=20,
                bgcolor="#16191E",
                border_radius=ft.BorderRadius.only(top_left=20, top_right=20)
            )
        ]),
        expand=True,
        bgcolor="#0F1115"
    )

    page.add(
        ft.Row([sidebar, chat_view], expand=True, spacing=0)
    )

# Run the app
if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)