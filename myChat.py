from pywebio import start_server
from pywebio.input import *
from pywebio.output import *
from pywebio.session import run_async, run_js, set_env, eval_js

import asyncio
import base64
import speech_recognition as sr
import tempfile
import os
import pyaudio
import wave

chat_msgs = []
online_users = set()

MAX_MESSAGES_COUNT = 400


def record_audio(duration=5, sample_rate=44100, chunk=1024, channels=1):
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=chunk)

    frames = []
    for i in range(0, int(sample_rate / chunk * (duration + 0.5))):
        data = stream.read(chunk)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
        wf = wave.open(temp_audio.name, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        return temp_audio.name


async def main():
    global chat_msgs
    set_env(title="CML Messenger")

    run_js("""
document.body.style.backgroundColor = 'black';
document.body.style.color = 'white';

// Style for all divs
var divs = document.getElementsByTagName('div');
for (var i = 0; i < divs.length; i++) {
    divs[i].style.backgroundColor = 'black';
    divs[i].style.color = 'white';
}

// Style for inputs
var inputs = document.getElementsByTagName('input');
for (var i = 0; i < inputs.length; i++) {
    inputs[i].style.backgroundColor = '#333';
    inputs[i].style.color = 'white';
    inputs[i].style.border = '1px solid #555';
}

// Style for buttons
var buttons = document.getElementsByTagName('button');
for (var i = 0; i < buttons.length; i++) {
    buttons[i].style.backgroundColor = '#444';
    buttons[i].style.color = 'white';
    buttons[i].style.border = '1px solid #666';
}

// Style for cards
var cards = document.getElementsByClassName('card');
for (var i = 0; i < cards.length; i++) {
    cards[i].style.backgroundColor = '#222';
    cards[i].style.border = '1px solid #444';
}

// Style for card headers
var cardHeaders = document.getElementsByClassName('card-header');
for (var i = 0; i < cardHeaders.length; i++) {
    cardHeaders[i].style.backgroundColor = '#333';
    cardHeaders[i].style.color = 'white';
    cardHeaders[i].style.borderBottom = '1px solid #444';
}

// Style for form submit buttons
var submitBtns = document.getElementsByClassName('ws-form-submit-btns')[0];
if (submitBtns) {
    submitBtns.style.backgroundColor = '#222';
}

// Translate buttons
var submitBtn = document.querySelector('.ws-form-submit-btns .btn-primary');
if (submitBtn) submitBtn.textContent = 'Send';

var resetBtn = document.querySelector('.ws-form-submit-btns .btn-warning');
if (resetBtn) resetBtn.textContent = 'Reset';

// Add an observer to apply styles to dynamically added elements
var observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.addedNodes) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) {  // ELEMENT_NODE
                    node.style.backgroundColor = 'black';
                    node.style.color = 'white';
                    if (node.tagName === 'INPUT') {
                        node.style.backgroundColor = '#333';
                        node.style.border = '1px solid #555';
                    }
                    if (node.tagName === 'BUTTON') {
                        node.style.backgroundColor = '#444';
                        node.style.border = '1px solid #666';
                    }
                    if (node.classList.contains('card')) {
                        node.style.backgroundColor = '#222';
                        node.style.border = '1px solid #444';
                    }
                    if (node.classList.contains('card-header')) {
                        node.style.backgroundColor = '#333';
                        node.style.borderBottom = '1px solid #444';
                    }
                }
            });
        }
    });
});

observer.observe(document.body, { childList: true, subtree: true });
""")

    put_markdown('## Welcome to our chat!!!')
    put_text(
        "Welcome to the chat for communication! Here you can chat with people from different parts of the world and share your thoughts and ideas in real-time. Be polite and respect other chat participants, and you will surely find new interesting interlocutors!")
    msg_box = output()
    put_scrollable(msg_box, height=300, keep_bottom=True)

    nickname = await input('Enter chat', required=True, placeholder='Your name',
                           validate=lambda n: "This nickname is already in use" if n in online_users or n == '*' else None)
    online_users.add(nickname)

    chat_msgs.append(('User', f"`{nickname}` has joined the chat!"))
    msg_box.append(put_markdown(f"`{nickname}` has joined the chat!"))

    refresh_task = run_async(refresh_msg(nickname, msg_box))

    while True:
        data = await input_group("New message!", [
            input(placeholder="Message text", name="msg"),
            file_upload(label="Upload image", name="image", accept="image/*"),
            actions(name="cmd",
                    buttons=["Send", 'Record voice message', {'label': "Leave chat", 'type': 'cancel'}])
        ], validate=lambda m: ('msg', 'Enter message text!') if m["cmd"] == 'Send' and not m["msg"] else None)

        if data is None:
            break

        if data['cmd'] == 'Record voice message':
            toast("Voice message recording will start in 3 seconds...")
            await asyncio.sleep(3)
            toast("Recording voice message...")

            audio_file = record_audio(duration=6)

            recognizer = sr.Recognizer()
            try:
                with sr.AudioFile(audio_file) as source:
                    audio = recognizer.record(source)
                    text = recognizer.recognize_google(audio, language="en-US")
                    msg_box.append(put_markdown(f"`{nickname}`: {text} (voice message)"))
                    chat_msgs.append((nickname, text))
            except sr.UnknownValueError:
                msg_box.append(put_markdown(f"`{nickname}`: Voice message not recognized"))
                chat_msgs.append((nickname, "Voice message not recognized"))
            except Exception as e:
                msg_box.append(put_markdown(f"`{nickname}`: Error processing voice message: {str(e)}"))
                chat_msgs.append((nickname, f"Error processing voice message: {str(e)}"))

            with open(audio_file, "rb") as audio:
                audio_data = base64.b64encode(audio.read()).decode('utf-8')

            audio_html = f'<audio controls src="data:audio/wav;base64,{audio_data}"></audio>'
            msg_box.append(put_html(audio_html))
            chat_msgs.append((nickname, audio_html))

            os.unlink(audio_file)
            continue

        if data['msg']:
            msg_box.append(put_markdown(f"`{nickname}`: {data['msg']}"))
            chat_msgs.append((nickname, data['msg']))

        if data['image']:
            img_url = put_image(data['image']['content'])
            msg_box.append(put_markdown(f"`{nickname}`: Image"))
            msg_box.append(img_url)
            chat_msgs.append((nickname, img_url))

    refresh_task.close()

    online_users.remove(nickname)
    toast("You have left the chat!")
    msg_box.append(put_markdown(f"User `{nickname}` has left the chat!"))
    chat_msgs.append(('This', f"User `{nickname}` has left the chat!"))

    put_buttons(["Rejoin"], onclick=lambda btn: run_js('window.location.reload()'))


async def refresh_msg(nickname, msg_box):
    global chat_msgs
    last_idx = len(chat_msgs)

    while True:
        await asyncio.sleep(1)

        for m in chat_msgs[last_idx:]:
            if m[0] != nickname:
                msg_box.append(put_markdown(f"`{m[0]}`: {m[1]}"))

        if len(chat_msgs) > MAX_MESSAGES_COUNT:
            chat_msgs = chat_msgs[len(chat_msgs) // 2:]

        last_idx = len(chat_msgs)


if __name__ == "__main__":
    start_server(main, debug=True, port=8000, cdn=False)