"""Analysiert das rohe SIP-Audio und konvertiert es zu WAV."""

import numpy as np
import wave
import os

def get_ulaw_decode_table() -> list[int]:
    """G.711 u-law Dekodierungstabelle."""
    table = []
    for i in range(256):
        val = ~i & 0xFF
        sign = val & 0x80
        exponent = (val >> 4) & 0x07
        mantissa = val & 0x0F
        
        sample = ((mantissa << 3) + 0x84) << (exponent)
        sample = sample - 0x84
        
        if sign:
            sample = -sample
        
        table.append(sample)
    return table

def get_alaw_decode_table() -> list[int]:
    """G.711 a-law Dekodierungstabelle."""
    table = []
    for i in range(256):
        val = i ^ 0x55
        sign = val & 0x80
        exponent = (val >> 4) & 0x07
        mantissa = val & 0x0F
        
        if exponent == 0:
            sample = (mantissa << 4) + 8
        else:
            sample = ((mantissa << 4) + 0x108) << (exponent - 1)
        
        if sign:
            sample = -sample
        
        table.append(sample)
    return table

def analyze_audio(data: bytes) -> dict:
    """Analysiert die Audio-Daten."""
    arr = np.frombuffer(data, dtype=np.uint8)
    
    return {
        "length": len(data),
        "min": int(arr.min()),
        "max": int(arr.max()),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "unique_values": len(np.unique(arr)),
        "first_10_bytes": list(arr[:10]),
        "is_silence": arr.std() < 5,
    }

def decode_and_save(data: bytes, output_path: str, codec: str = "ulaw"):
    """Dekodiert Audio und speichert als WAV."""
    if codec == "ulaw":
        table = get_ulaw_decode_table()
    else:
        table = get_alaw_decode_table()
    
    # Dekodiere zu 16-bit PCM
    samples = np.array([table[b] for b in data], dtype=np.int16)
    
    # Speichere als WAV (8kHz mono)
    with wave.open(output_path, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(8000)
        wav.writeframes(samples.tobytes())
    
    return samples

def save_raw_as_pcm(data: bytes, output_path: str):
    """Speichert rohe Bytes als 8kHz 8-bit WAV (ohne Dekodierung)."""
    # Konvertiere 8-bit unsigned zu 16-bit signed
    arr = np.frombuffer(data, dtype=np.uint8).astype(np.int16)
    arr = (arr - 128) * 256  # Zentriere und skaliere
    
    with wave.open(output_path, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(arr.astype(np.int16).tobytes())

def main():
    input_file = "recordings/sip_audio_raw.pcm"
    
    if not os.path.exists(input_file):
        print(f"Datei nicht gefunden: {input_file}")
        return
    
    with open(input_file, "rb") as f:
        data = f.read()
    
    print(f"\n=== Audio-Analyse ===")
    stats = analyze_audio(data)
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Speichere verschiedene Versionen zum Testen
    print(f"\n=== Konvertiere zu WAV ===")
    
    # Version 1: Als u-law dekodiert
    decode_and_save(data, "recordings/sip_audio_ulaw.wav", "ulaw")
    print(f"  Gespeichert: recordings/sip_audio_ulaw.wav (u-law dekodiert)")
    
    # Version 2: Als a-law dekodiert
    decode_and_save(data, "recordings/sip_audio_alaw.wav", "alaw")
    print(f"  Gespeichert: recordings/sip_audio_alaw.wav (a-law dekodiert)")
    
    # Version 3: Raw als PCM (ohne Dekodierung)
    save_raw_as_pcm(data, "recordings/sip_audio_raw8bit.wav")
    print(f"  Gespeichert: recordings/sip_audio_raw8bit.wav (raw 8-bit)")
    
    print(f"\n=== Bitte die WAV-Dateien anhören ===")
    print("Welche klingt richtig?")
    print("  - sip_audio_ulaw.wav: Wenn Sipgate G.711 u-law (PCMU) verwendet")
    print("  - sip_audio_alaw.wav: Wenn Sipgate G.711 a-law (PCMA) verwendet")
    print("  - sip_audio_raw8bit.wav: Wenn es bereits lineares PCM ist")

if __name__ == "__main__":
    main()
