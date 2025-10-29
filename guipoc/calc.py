#!/usr/bin/env python3

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

class MainApp(App):
    def build(self):
        self.operators = ["/", "*", "+", "-"]
        self.last_was_operator = None
        self.last_button = None
        main_layout = BoxLayout(orientation="vertical")
        self.solution = TextInput(
            multiline=False, readonly=True, halign="right", font_size=55
        )
        main_layout.add_widget(self.solution)
        buttons = [
            ["0", "1", "2", "3"],
            ["4", "5", "6", "7"],
            ["8", "9", "A", "B"],
            ["C", "D", "E", "F"],
        ]
        for row in buttons:
            h_layout = BoxLayout()
            for label in row:
                button = Button(
                    text=label,
                    pos_hint={"center_x": 0.5, "center_y": 0.5},
                )
                button.bind(on_press=self.on_button_press)
                h_layout.add_widget(button)
            main_layout.add_widget(h_layout)

        h_layout = BoxLayout()

        clear_button = Button(
            text="Clear", pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        clear_button.bind(on_press=self.on_clear)
        h_layout.add_widget(clear_button)

        call_button = Button(
            text="Call", pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        call_button.bind(on_press=self.on_call)
        h_layout.add_widget(call_button)

        main_layout.add_widget(h_layout)

        return main_layout

    def on_button_press(self, instance):
        current = self.solution.text
        button_text = instance.text

        if button_text == "C":
            # Clear the solution widget
            self.solution.text = ""
        else:
            if current and (
                self.last_was_operator and button_text in self.operators):
                # Don't add two operators right after each other
                return
            elif current == "" and button_text in self.operators:
                # First character is unable to be an operator
                return
            else:
                new_text = current + button_text
                self.solution.text = new_text
        self.last_button = button_text
        self.last_was_operator = self.last_button in self.operators

    def on_clear(self, instance):
        self.solution.text = ""

    def call(self, to):
        self.solution.text = "Appel en cours..."

    def on_call(self, instance):
        to = self.solution.text
        self.call(to)

if __name__ == "__main__":
    app = MainApp()
    app.run()
