"""Analysiert die AI Audio Debug-Dateien."""
import numpy as np
import wave
import audioop

def analyze_pcm(filename, sample_rate, sample_width, description):
    """Analysiert eine PCM-Datei."""
    print(f"\n=== {description} ===")
    print(f"Datei: {filename}")
    
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        print(f"Größe: {len(data)} bytes")
        
        if sample_width == 2:
            samples = np.frombuffer(data, dtype=np.int16)
            print(f"Samples: {len(samples)}")
            print(f"Dauer: {len(samples) / sample_rate:.2f}s")
            print(f"Min: {samples.min()}, Max: {samples.max()}")
            print(f"Mean: {samples.mean():.1f}, Std: {samples.std():.1f}")
            
            # Speichere als WAV
            wav_name = filename.replace('.pcm', '.wav')
            with wave.open(wav_name, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(data)
            print(f"Gespeichert als: {wav_name}")
            
        elif sample_width == 1:
            samples = np.frombuffer(data, dtype=np.uint8)
            print(f"Samples: {len(samples)}")
            print(f"Dauer: {len(samples) / sample_rate:.2f}s")
            print(f"Min: {samples.min()}, Max: {samples.max()}")
            print(f"Mean: {samples.mean():.1f}")
            
            # A-law dekodieren und als WAV speichern
            try:
                decoded = audioop.alaw2lin(data, 2)
                wav_name = filename.replace('.pcm', '_decoded.wav')
                with wave.open(wav_name, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(decoded)
                print(f"A-law dekodiert und gespeichert als: {wav_name}")
            except Exception as e:
                print(f"A-law Dekodierung fehlgeschlagen: {e}")
                
    except FileNotFoundError:
        print("Datei nicht gefunden!")
    except Exception as e:
        print(f"Fehler: {e}")

# Analysiere AI Audio (24kHz, 16-bit)
analyze_pcm("recordings/ai_audio_24k.pcm", 24000, 2, "AI Audio (Original 24kHz 16-bit)")

# Analysiere konvertiertes Audio (8kHz, A-law = 8-bit)
analyze_pcm("recordings/ai_audio_8k_alaw.pcm", 8000, 1, "Konvertiertes Audio (8kHz A-law)")

print("\n" + "="*50)
print("Bitte die WAV-Dateien anhören:")
print("  - recordings/ai_audio_24k.wav (Original von AI)")
print("  - recordings/ai_audio_8k_alaw_decoded.wav (Nach Konvertierung)")
print("="*50)
