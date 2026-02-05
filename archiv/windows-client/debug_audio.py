"""Debug-Skript um SIP Audio zu analysieren und verschiedene Formate zu testen."""

import numpy as np
import wave
import os

def analyze_and_convert():
    input_file = "recordings/sip_audio_raw.pcm"
    
    if not os.path.exists(input_file):
        print(f"Datei nicht gefunden: {input_file}")
        return
    
    with open(input_file, "rb") as f:
        data = f.read()
    
    print(f"\n=== Audio-Analyse ===")
    print(f"Dateigröße: {len(data)} bytes")
    
    # Analysiere als 8-bit
    arr_8bit = np.frombuffer(data, dtype=np.uint8)
    print(f"\nAls 8-bit unsigned:")
    print(f"  Min: {arr_8bit.min()}, Max: {arr_8bit.max()}, Mean: {arr_8bit.mean():.1f}")
    print(f"  Erste 20: {list(arr_8bit[:20])}")
    
    # Finde echte Daten (nicht 0x80)
    non_silence = arr_8bit[arr_8bit != 128]
    if len(non_silence) > 0:
        print(f"  Nicht-Stille Samples: {len(non_silence)}")
        print(f"  Nicht-Stille Min: {non_silence.min()}, Max: {non_silence.max()}")
    
    print(f"\n=== Konvertiere zu verschiedenen WAV-Formaten ===")
    
    # Version 1: 8-bit unsigned PCM → 16-bit signed (wie im Code)
    samples_16bit = (arr_8bit.astype(np.int16) - 128) * 256
    save_wav("recordings/debug_8bit_to_16bit_8khz.wav", samples_16bit, 8000)
    print("  debug_8bit_to_16bit_8khz.wav - 8-bit unsigned als 16-bit, 8kHz")
    
    # Version 2: Direkt als 8-bit WAV
    save_wav_8bit("recordings/debug_8bit_raw_8khz.wav", arr_8bit, 8000)
    print("  debug_8bit_raw_8khz.wav - Original 8-bit, 8kHz")
    
    # Version 3: Als u-law dekodiert
    ulaw_decoded = decode_ulaw(data)
    save_wav("recordings/debug_ulaw_decoded_8khz.wav", ulaw_decoded, 8000)
    print("  debug_ulaw_decoded_8khz.wav - u-law dekodiert, 8kHz")
    
    # Version 4: Als a-law dekodiert
    alaw_decoded = decode_alaw(data)
    save_wav("recordings/debug_alaw_decoded_8khz.wav", alaw_decoded, 8000)
    print("  debug_alaw_decoded_8khz.wav - a-law dekodiert, 8kHz")
    
    print(f"\n=== Bitte die WAV-Dateien in recordings/ anhören ===")
    print("Die Datei die am besten klingt zeigt das richtige Format!")

def save_wav(path: str, samples: np.ndarray, sample_rate: int):
    """Speichert 16-bit signed PCM als WAV."""
    with wave.open(path, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.astype(np.int16).tobytes())

def save_wav_8bit(path: str, samples: np.ndarray, sample_rate: int):
    """Speichert 8-bit unsigned PCM als WAV."""
    with wave.open(path, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(1)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.astype(np.uint8).tobytes())

def decode_ulaw(data: bytes) -> np.ndarray:
    """Dekodiert G.711 u-law zu 16-bit signed PCM."""
    BIAS = 0x84
    CLIP = 32635
    
    exp_lut = [0, 132, 396, 924, 1980, 4092, 8316, 16764]
    
    samples = []
    for byte in data:
        byte = ~byte & 0xFF
        sign = (byte & 0x80)
        exponent = (byte >> 4) & 0x07
        mantissa = byte & 0x0F
        
        sample = exp_lut[exponent] + (mantissa << (exponent + 3))
        
        if sign:
            sample = -sample
        
        samples.append(sample)
    
    return np.array(samples, dtype=np.int16)

def decode_alaw(data: bytes) -> np.ndarray:
    """Dekodiert G.711 a-law zu 16-bit signed PCM."""
    samples = []
    for byte in data:
        byte ^= 0x55
        sign = byte & 0x80
        exponent = (byte >> 4) & 0x07
        mantissa = byte & 0x0F
        
        if exponent == 0:
            sample = (mantissa << 4) + 8
        else:
            sample = ((mantissa << 4) + 0x108) << (exponent - 1)
        
        if sign:
            sample = -sample
        
        samples.append(sample)
    
    return np.array(samples, dtype=np.int16)

if __name__ == "__main__":
    analyze_and_convert()
