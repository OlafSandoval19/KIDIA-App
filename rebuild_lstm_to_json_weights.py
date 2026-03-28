from pathlib import Path
from tensorflow.keras.models import load_model, Sequential
from tensorflow.keras.layers import Input, LSTM, Dropout, Dense

root = Path("models/LSTM")

for child_dir in sorted(root.iterdir()):
    if not child_dir.is_dir():
        continue

    keras_path = child_dir / "model.keras"
    arch_path = child_dir / "model_architecture.json"
    weights_path = child_dir / "model_clean.weights.h5"

    if not keras_path.exists():
        print(f"[SKIP] No existe {keras_path}")
        continue

    print(f"[INFO] Procesando {child_dir.name}")

    old_model = load_model(keras_path, compile=False, safe_mode=False)

    new_model = Sequential([
        Input(shape=(360, 5)),
        LSTM(32, return_sequences=False),
        Dropout(0.2),
        Dense(64, activation="relu"),
        Dense(360, activation="linear"),
    ])

    new_model.set_weights(old_model.get_weights())

    with open(arch_path, "w", encoding="utf-8") as f:
        f.write(new_model.to_json())

    new_model.save_weights(weights_path)

    print(f"[OK] Guardados: {arch_path.name} y {weights_path.name}")

print("Listo.")