#!/usr/bin/env python3
"""
Yelp - Produktionsversion mit Tageszeit-abhängigen Antworten
H2n USB-Mikrofon + Piper TTS + Rotating Log
Ruferkennung: nur "hallo" und "hilfe"
"""

import pyaudio
import numpy as np
import whisper
import time
import wave
import tempfile
import os
from datetime import datetime
import queue
import subprocess
import json
from logging.handlers import RotatingFileHandler
import logging

# ============== KONFIGURATION ==============
RATE = 16000              # Jabra Speak2 55: 16kHz (changed from 48000)
CHUNK = 1024              # Smaller chunks for 16kHz (changed from 2048)
CHANNELS = 1              # Jabra: Mono (changed from 2)

# Rufererkennung - Fine-Tuning Parameter
RUF_SCHWELLE = 0.0005         # Lautstärke-Schwelle - lowered for Jabra room mic
STILLE_DAUER = 1.0            # Sekunden Stille nach Ruf (0.5-2.0)
MIN_AUDIO_LAENGE = 0.1        # Minimale Audio-Länge in Sekunden (verhindert zu kurze Aufnahmen)
PAUSE_NACH_ANTWORT = 5        # Cooldown zwischen Antworten in Sekunden

# Whisper Fine-Tuning Parameter
WHISPER_TEMPERATURE = 0.0     # 0.0=deterministisch, 0.2-0.8=kreativer (Standard: 0.0)
WHISPER_BEAM_SIZE = 5         # 1-10, höher=genauer aber langsamer (Standard: 5)
WHISPER_BEST_OF = 5           # Anzahl Kandidaten (Standard: 5)
WHISPER_PATIENCE = 1.0        # Beam search patience (Standard: 1.0)

AUDIO_DEVICE_NAME = "default"  # Use "default" device name (more reliable than index)

# Piper mit vollständigem Pfad
PIPER_BINARY = "/home/ljung/yelp/venv/bin/piper"
PIPER_MODEL = "/home/ljung/yelp/piper_voices/de_DE-kerstin-low.onnx"
PIPER_SPEECH_SPEED = 1.5  # 1.0=normal, 1.5=slower, 2.0=very slow
SILENCE_FILE = "/home/ljung/yelp/speaker_init.wav"  # Wakeup tone + silence

# Log-Dateien mit Rotation
LOG_DIR = "/home/ljung/yelp/logs"
LOG_FILE = os.path.join(LOG_DIR, "yelp.log")
JSON_LOG_FILE = os.path.join(LOG_DIR, "yelp_events.json")

# Temporäre Dateien - nutze eigenes Verzeichnis statt /tmp
TEMP_DIR = "/home/ljung/yelp/temp"

# Log-Rotation: Max 10 MB pro Datei, 3 Backup-Dateien
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 3

# ============== ANTWORTEN NACH TAGESZEIT ==============
# Zeitbereiche: Nacht (22-6 Uhr), Morgen (6-12 Uhr), Tag (12-18 Uhr), Abend (18-22 Uhr)

ANTWORTEN_NACHT = [
    "Du kannst ruhig weiter schlafen, ich passe auf dich auf.",
    "Alles ist gut, ich bin bei dir.",
    "Ich bin hier.",
    "Du bist nicht allein.",
    "Ich bin da, keine Sorge.",
    "Alles ist in Ordnung.",
]

ANTWORTEN_MORGEN = [
    "Guten Morgen, ich bin hier.",
    "Alles ist gut, ich bin bei dir.",
    "Ich bin da, keine Sorge.",
    "Du bist nicht allein.",
    "Ja, ich bin hier.",
    "Ich passe auf dich auf, alles ist gut.",
]

ANTWORTEN_TAG = [
    "Alles ist gut, ich bin bei dir.",
    "Ich bin hier.",
    "Ja, ich bin hier.",
    "Du bist nicht allein.",
    "Ich bin da, keine Sorge.",
    "Ich passe auf dich auf, alles ist gut, mach dir keine Sorgen.",
    "Alles ist in Ordnung.",
]

ANTWORTEN_ABEND = [
    "Ich bin hier.",
    "Alles ist gut, ich bin bei dir.",
    "Ja, ich bin hier.",
    "Du bist nicht allein.",
    "Ich passe auf dich auf, alles ist gut.",
    "Alles ist in Ordnung, ich bin da.",
]

def get_antworten_fuer_tageszeit():
    """Gibt die passenden Antworten für die aktuelle Tageszeit zurück"""
    stunde = datetime.now().hour

    if 22 <= stunde or stunde < 6:
        # Nacht: 22:00 - 05:59
        return "NACHT", ANTWORTEN_NACHT
    elif 6 <= stunde < 12:
        # Morgen: 06:00 - 11:59
        return "MORGEN", ANTWORTEN_MORGEN
    elif 12 <= stunde < 18:
        # Tag: 12:00 - 17:59
        return "TAG", ANTWORTEN_TAG
    else:
        # Abend: 18:00 - 21:59
        return "ABEND", ANTWORTEN_ABEND

# ============== LOGGING SETUP ==============
def setup_logging():
    """Richtet rotierendes Logging ein"""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger('yelp')
    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger

class JSONRotatingFileHandler:
    """Eigener JSON-Log-Handler mit Rotation"""
    def __init__(self, filename, max_bytes, backup_count):
        self.filename = filename
        self.max_bytes = max_bytes
        self.backup_count = backup_count

    def write(self, event):
        if os.path.exists(self.filename):
            if os.path.getsize(self.filename) >= self.max_bytes:
                self.rotate()

        with open(self.filename, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def rotate(self):
        for i in range(self.backup_count - 1, 0, -1):
            src = f"{self.filename}.{i}"
            dst = f"{self.filename}.{i + 1}"
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.rename(src, dst)

        if os.path.exists(self.filename):
            os.rename(self.filename, f"{self.filename}.1")

logger = setup_logging()
json_handler = JSONRotatingFileHandler(JSON_LOG_FILE, MAX_LOG_SIZE, BACKUP_COUNT)

def log_event(event_type, message, details=None):
    """Schreibt Event in beide Log-Dateien mit Rotation"""
    if event_type == "ERROR":
        logger.error(f"{event_type}: {message}" + (f" | {details}" if details else ""))
    else:
        logger.info(f"{event_type}: {message}" + (f" | {details}" if details else ""))

    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "message": message
    }
    if details:
        event["details"] = details

    json_handler.write(event)

# ============== INITIALISIERUNG ==============
# Erstelle temp-Verzeichnis falls nicht vorhanden
os.makedirs(TEMP_DIR, exist_ok=True)

print("Lade Whisper Modell (CPU-only)...")
whisper_model = whisper.load_model("tiny", device="cpu")
print("✓ Whisper geladen!")

log_event("SYSTEM_START", "Yelp gestartet")

audio_queue = queue.Queue()
letzte_antwort_zeit = 0
antwort_counter = {}  # Dictionary für Counter pro Tageszeit

# ============== AUDIO-FUNKTIONEN ==============
def audio_callback(in_data, frame_count, time_info, status):
    audio_queue.put(in_data)
    return (in_data, pyaudio.paContinue)

def ist_laut_genug(audio_data):
    audio_np = np.frombuffer(audio_data, dtype=np.int16)
    if CHANNELS == 2:
        audio_np = audio_np.reshape(-1, 2).mean(axis=1)

    # Avoid sqrt of negative/zero values
    mean_square = np.mean(audio_np**2)
    if mean_square <= 0:
        return False

    rms = np.sqrt(mean_square)
    normalized_rms = rms / 32768.0
    return normalized_rms > RUF_SCHWELLE

def speichere_audio(frames, filename):
    # Jabra already records at 16kHz mono - no conversion needed!
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

# ============== SPRACHERKENNUNG ==============
def erkenne_ruf(audio_file):
    try:
        # Whisper mit Fine-Tuning Parametern
        result = whisper_model.transcribe(
            audio_file,
            language="de",
            fp16=False,
            temperature=WHISPER_TEMPERATURE,
            beam_size=WHISPER_BEAM_SIZE,
            best_of=WHISPER_BEST_OF,
            patience=WHISPER_PATIENCE,
            condition_on_previous_text=False,  # Verhindert Kontext-Fehler
            no_speech_threshold=0.6,           # Höher = ignoriert mehr Nicht-Sprache
            logprob_threshold=-1.0,            # Schwelle für Qualität
        )

        text = result["text"].strip().lower()

        # Prüfe ob Text leer ist (häufiges Problem)
        if not text or len(text) < 2:
            log_event("WHISPER_LEER", "Whisper hat leeren Text erkannt", {"segments": len(result.get("segments", []))})
            return False, text

        # NUR "hallo" und "hilfe" erkennen
        ruf_woerter = ["hallo", "hilfe"]
        ist_ruf_erkannt = any(wort in text for wort in ruf_woerter)

        return ist_ruf_erkannt, text

    except Exception as e:
        log_event("ERROR", "Fehler bei Spracherkennung", str(e))
        return False, ""

# ============== SPRACHAUSGABE ==============
def antworte(text, antwort_nummer, tageszeit):
    temp_file = None
    try:
        temp_file = os.path.join(TEMP_DIR, f"yelp_antwort_{antwort_nummer}.wav")

        # Generate speech with Piper (with speed control)
        process = subprocess.Popen(
            [PIPER_BINARY, "--model", PIPER_MODEL, "--length_scale", str(PIPER_SPEECH_SPEED), "--output_file", temp_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=text.encode('utf-8'))

        if process.returncode != 0:
            log_event("ERROR", "Piper TTS Fehler", stderr.decode())
            return False

        # Verify Piper created the file
        if not os.path.exists(temp_file):
            log_event("ERROR", "Piper hat keine Audio-Datei erstellt")
            return False

        # Play silence first to wake up speaker, then the answer
        # Convert mono to stereo for Jabra speaker (expects 2 channels)
        temp_stereo = os.path.join(TEMP_DIR, f"yelp_antwort_{antwort_nummer}_stereo.wav")

        # Convert mono Piper output to stereo for playback
        subprocess.run([
            'ffmpeg', '-loglevel', 'error', '-i', temp_file,
            '-ac', '2', '-y', temp_stereo
        ], capture_output=True)

        if os.path.exists(SILENCE_FILE):
            os.system(f"aplay -q -D plughw:0,0 {SILENCE_FILE} && aplay -q -D plughw:0,0 {temp_stereo}")
        else:
            # Fallback if silence file missing
            time.sleep(0.5)
            os.system(f"aplay -q -D plughw:0,0 {temp_stereo}")

        # Cleanup stereo file
        if os.path.exists(temp_stereo):
            os.remove(temp_stereo)

        return True

    except Exception as e:
        log_event("ERROR", "Fehler bei Sprachausgabe", str(e))
        return False
    finally:
        # Always cleanup temp file, even if error occurs
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

# ============== HAUPTSCHLEIFE ==============
def main():
    global letzte_antwort_zeit, antwort_counter

    tageszeit, antworten = get_antworten_fuer_tageszeit()

    # Find device index by name (more reliable than fixed index)
    p = pyaudio.PyAudio()
    device_index = None

    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if AUDIO_DEVICE_NAME in info['name'].lower():
                device_index = i
                mic_name = info['name']
                break
        except:
            continue

    if device_index is None:
        log_event("ERROR", f"Audio device '{AUDIO_DEVICE_NAME}' not found, using default")
        device_index = None  # Let PyAudio choose default
        mic_name = "System Default"

    log_event("SYSTEM_INFO", f"Mikrofon: {mic_name} (Index: {device_index}, {RATE} Hz, {CHANNELS} Kanäle)")
    log_event("SYSTEM_INFO", f"Rufererkennung - Schwelle: {RUF_SCHWELLE}, Stille: {STILLE_DAUER}s, Min-Länge: {MIN_AUDIO_LAENGE}s")
    log_event("SYSTEM_INFO", f"Whisper - Temp: {WHISPER_TEMPERATURE}, Beam: {WHISPER_BEAM_SIZE}, BestOf: {WHISPER_BEST_OF}")
    log_event("SYSTEM_INFO", f"Tageszeit: {tageszeit}, Antworten: {len(antworten)}")
    log_event("SYSTEM_INFO", f"Log-Rotation: Max {MAX_LOG_SIZE // (1024*1024)} MB, {BACKUP_COUNT} Backups")

    stream = p.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK,
        stream_callback=audio_callback
    )

    stream.start_stream()

    audio_buffer = []
    stille_counter = 0
    aufnahme_aktiv = False
    aufnahme_start_zeit = 0

    try:
        while stream.is_active():
            try:
                data = audio_queue.get(timeout=1)
            except queue.Empty:
                continue

            if ist_laut_genug(data):
                if not aufnahme_aktiv:
                    aufnahme_aktiv = True
                    aufnahme_start_zeit = time.time()
                audio_buffer.append(data)
                stille_counter = 0
            else:
                if aufnahme_aktiv:
                    audio_buffer.append(data)
                    stille_counter += 1

                    if stille_counter > (STILLE_DAUER * RATE / CHUNK):
                        # Prüfe Mindestlänge der Aufnahme
                        aufnahme_dauer = time.time() - aufnahme_start_zeit

                        if aufnahme_dauer < MIN_AUDIO_LAENGE:
                            log_event("AUDIO_ZU_KURZ", f"Aufnahme zu kurz: {aufnahme_dauer:.2f}s (min: {MIN_AUDIO_LAENGE}s)")
                            audio_buffer = []
                            aufnahme_aktiv = False
                            stille_counter = 0
                            continue

                        zeit_seit_letzter_antwort = time.time() - letzte_antwort_zeit

                        # Audio verarbeiten
                        temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=TEMP_DIR)
                        speichere_audio(audio_buffer, temp_audio.name)

                        ist_ruf, erkannter_text = erkenne_ruf(temp_audio.name)
                        os.remove(temp_audio.name)

                        if ist_ruf:
                            if zeit_seit_letzter_antwort > PAUSE_NACH_ANTWORT:
                                # Tageszeit aktualisieren
                                tageszeit, antworten = get_antworten_fuer_tageszeit()

                                # Counter für diese Tageszeit initialisieren
                                if tageszeit not in antwort_counter:
                                    antwort_counter[tageszeit] = 0

                                # Antwort wählen
                                antwort = antworten[antwort_counter[tageszeit] % len(antworten)]
                                antwort_counter[tageszeit] += 1

                                # LOG: Ruf erkannt
                                log_event(
                                    "RUF_ERKANNT",
                                    f"'{erkannter_text}' -> '{antwort}' [{tageszeit}]",
                                    {
                                        "erkannter_text": erkannter_text,
                                        "antwort": antwort,
                                        "tageszeit": tageszeit,
                                        "aufnahme_dauer": round(aufnahme_dauer, 2)
                                    }
                                )

                                # Pause microphone while playing answer (prevent feedback loop)
                                stream.stop_stream()

                                # Antwort abspielen
                                erfolg = antworte(antwort, antwort_counter[tageszeit], tageszeit)

                                if erfolg:
                                    letzte_antwort_zeit = time.time()
                                else:
                                    log_event("ERROR", "Antwort konnte nicht abgespielt werden")

                                # Resume microphone
                                stream.start_stream()
                            else:
                                # Cooldown aktiv
                                verbleibend = int(PAUSE_NACH_ANTWORT - zeit_seit_letzter_antwort)
                                log_event(
                                    "RUF_IGNORIERT_COOLDOWN",
                                    f"'{erkannter_text}' (Cooldown: {verbleibend}s)",
                                    {"erkannter_text": erkannter_text, "cooldown_verbleibend": verbleibend}
                                )

                        audio_buffer = []
                        aufnahme_aktiv = False
                        stille_counter = 0

    except KeyboardInterrupt:
        log_event("SYSTEM_STOP", "Programm durch Benutzer beendet")

    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()
