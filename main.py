import os
import re
import asyncio
import edge_tts
import threading
import requests
from gtts import gTTS

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp

from kivy.core.window import Window
Window.clearcolor = (0.09, 0.55, 0.87, 1)
Window.softinput_mode = "below_target"
OPENAI_API_KEY = "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"
SYSTEM_PROMPT = (
    "Ты — дерзкий, остроумный и саркастичный собеседник. "
    "Никакой вежливости: не извиняешься, не говоришь 'конечно' и 'рад помочь'. "
    "Отвечаешь коротко, с иронией, можешь подкалывать, но по существу и полезно. "
    "Пиши по-русски, живым разговорным языком. "
    "Язви, но не оскорбляй по национальности, полу и внешности."
)

SEARCH_WORDS = ("найди", "поищи", "что такое", "кто такой", "кто такая",
                "новости", "погугли", "когда", "где", "сколько", "цена")


def needs_search(text):
    t = text.lower()
    return any(w in t for w in SEARCH_WORDS)


def search_web(query):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        res = DDGS().text(query, max_results=4)
        return "\n".join(r["title"] + ": " + r["body"] for r in res)
    except Exception as e:
        print("Поиск не сработал:", e)
        return ""


def ask_gpt(messages):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": "Bearer " + OPENAI_API_KEY}
    data = {"model": "openai/gpt-oss-20b", "messages": messages}
    r = requests.post(url, headers=headers, json=data, timeout=90)
    answer = r.json()
    if "choices" in answer:
        return answer["choices"][0]["message"]["content"]
    return "Нейросеть ответила ошибкой: " + str(answer)


VOICE = "ru-RU-DmitryNeural"

def clean_for_voice(text):
    return re.sub(r"[#*_`()>~|]", " ", text).strip()

def make_voice(text):
    path = os.path.abspath("reply.mp3")
    try:
        async def gen():
            tts = edge_tts.Communicate(text, VOICE, rate="+35%")
            await tts.save(path)
        asyncio.run(gen())
    except Exception as e:
        print("Edge-TTS не сработал, включаю робота:", e)
        from gtts import gTTS
        gTTS(text=clean_for_voice(text), lang="ru").save(path)
    return path


def play_voice(path):
    try:
        from jnius import autoclass
        MediaPlayer = autoclass("android.media.MediaPlayer")
        player = MediaPlayer()
        player.setDataSource(path)
        player.prepare()
        player.start()
    except Exception as e:
        print("Голос не заиграл:", e)


class Bubble(BoxLayout):
    def __init__(self, text, mine=False, **kw):
        super().__init__(**kw)
        self.size_hint_y = None
        self.padding = [dp(10), dp(3)]
        lbl = Label(
            text=text,
            size_hint=(None, None),
            text_size=(Window.width * 0.72, None),
            halign="left",
            valign="middle",
            padding=[dp(12), dp(8)],
            color=(1, 1, 1, 1) if mine else (0.1, 0.1, 0.1, 1),
        )
        with lbl.canvas.before:
            Color(*(0.03, 0.37, 0.80, 1) if mine else (1, 1, 1, 1))
            bg = RoundedRectangle(radius=[dp(14)])
        lbl.bind(pos=lambda i, v: setattr(bg, "pos", i.pos))
        lbl.bind(size=lambda i, v: setattr(bg, "size", i.size))
        lbl.bind(texture_size=self._resize)
        self.lbl = lbl
        if mine:
            self.add_widget(Widget(size_hint_x=0.25))
            self.add_widget(lbl)
        else:
            self.add_widget(lbl)
            self.add_widget(Widget(size_hint_x=0.25))

    def _resize(self, i, v):
        i.size = v
        self.height = v[1] + dp(6)


class ChatApp(App):
    def build(self):
        self.title = "Мой бот"
        root = BoxLayout(orientation="vertical")

        header = BoxLayout(size_hint_y=None, height=dp(50), padding=[dp(12), 0])
        with header.canvas.before:
            Color(0.06, 0.47, 0.75, 1)
            self.header_rect = Rectangle()
        header.bind(pos=self._upd_header, size=self._upd_header)
        header.add_widget(Label(text="Чат", bold=True, color=(1, 1, 1, 1)))
        root.add_widget(header)

        self.scroll = ScrollView()
        self.chat = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=[dp(6), dp(6)],
        )
        self.chat.bind(minimum_height=self.chat.setter("height"))
        self.scroll.add_widget(self.chat)
        root.add_widget(self.scroll)

        bottom = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8), padding=[dp(8), dp(4)])
        self.input_field = TextInput(
            multiline=False,
            hint_text="Сообщение…",
            font_size=sp(16),
            background_color=(1, 1, 1, 1),
            foreground_color=(0.1, 0.1, 0.1, 1),
        )
        send_btn = Button(
            text="➤",
            size_hint_x=None,
            width=dp(60),
            background_normal="",
            background_color=(0.09, 0.55, 0.87, 1),
            font_size=sp(20),
        )
        send_btn.bind(on_press=self.on_send)
        self.input_field.bind(on_text_validate=self.on_send)
        bottom.add_widget(self.input_field)
        bottom.add_widget(send_btn)
        root.add_widget(bottom)

        self.history = []
        return root

    def _upd_header(self, i, v):
        self.header_rect.pos = i.pos
        self.header_rect.size = i.size

    def add_bubble(self, text, mine):
        b = Bubble(text=text, mine=mine)
        self.chat.add_widget(b)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.1)

    def on_send(self, *args):
        text = self.input_field.text.strip()
        if not text:
            return
        self.input_field.text = ""
        self.add_bubble("Вы: " + text, mine=True)
        self.typing = Bubble(text="Бот печатает…", mine=False)
        self.chat.add_widget(self.typing)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.1)
        threading.Thread(target=self.get_answer, args=(text,), daemon=True).start()

    def get_answer(self, text):
        try:
            msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history[-14:]
            if needs_search(text):
                web = search_web(text)
                if web:
                    msgs.append({"role": "system",
                                 "content": "Свежие данные из интернета:\n" + web})
            msgs.append({"role": "user", "content": text})
            reply = ask_gpt(msgs)
        except Exception as e:
            print("Ошибка запроса:", e)
            reply = "Связь с нейросетью оборвалась. Проверь интернет и попробуй ещё раз."
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": reply})
        Clock.schedule_once(lambda dt: self.show_answer(reply))

    def show_answer(self, reply):
        self.chat.remove_widget(self.typing)
        self.add_bubble("Бот: " + reply, mine=False)
        try:
            path = make_voice(reply)
            play_voice(path)
        except Exception as e:
            print("Голос не сработал:", e)


ChatApp().run()
