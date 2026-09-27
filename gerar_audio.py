import os
import subprocess
from gtts import gTTS
from pydub import AudioSegment
import imageio_ffmpeg

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
AudioSegment.converter = ffmpeg

numeros = {1: "Um", 2: "Dois", 3: "Três", 4: "Quatro", 5: "Cinco"}
pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
os.makedirs(pasta, exist_ok=True)

for n, palavra in numeros.items():
    mp3 = os.path.join(pasta, f"{n}_tmp.mp3")
    gTTS(text=palavra, lang="pt").save(mp3)

    raw = subprocess.run(
        [ffmpeg, "-v", "error", "-i", mp3, "-f", "s16le",
         "-acodec", "pcm_s16le", "-ac", "1", "-ar", "24000", "-"],
        capture_output=True, check=True,
    ).stdout

    som = AudioSegment(data=raw, sample_width=2, frame_rate=24000, channels=1)
    som.export(os.path.join(pasta, f"{n}.wav"), format="wav")
    os.remove(mp3)
    print(f"{n}.wav -> {palavra} ({len(som)}ms)")

print("Audios gerados!")
