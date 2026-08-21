import librosa
import sounddevice as sd
import numpy as np

sample_rate = 22050
duration = 1

def deteksi_chord(audio):
    chroma = librosa.feature.chroma_stft(y=audio, sr=sample_rate)
    note = np.argmax(np.mean(chroma, axis=1))
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    note_kenceng = np.argmax(note)

    print("note yang sering muncul:", note_names[note_kenceng])

while True:
    print("Mendegar...")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    audio = audio.flatten()
    deteksi_chord(audio)

