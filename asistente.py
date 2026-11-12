# Asistente Personal "Francheska" - hecho 100% en Python con Streamlit
import json
import urllib.request
import urllib.error
import streamlit as st

INSTRUCCION = ("Eres Francheska, un asistente personal amable, claro y experto en todos los temas. "
               "Responde siempre en el idioma del usuario.")


BASE = "https://generativelanguage.googleapis.com/v1beta"


def _pedir(url, clave, cuerpo=None, espera=40):
    peticion = urllib.request.Request(url, data=cuerpo, headers={
        "Content-Type": "application/json", "x-goog-api-key": clave})
    try:
        with urllib.request.urlopen(peticion, timeout=espera) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"({e.code}) {e.read().decode(errors='ignore')[:400]}")
    except Exception as e:  # tiempo agotado, internet lento, etc.
        raise RuntimeError(f": Google tardó demasiado en responder ({e}). Revisa tu internet e inténtalo otra vez.")


@st.cache_data(show_spinner=False)
def modelos_disponibles(clave):
    """Pregunta a Google qué modelos puede usar ESTA clave."""
    nombres, url = [], f"{BASE}/models?pageSize=1000"
    datos = _pedir(url, clave)
    for m in datos.get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            nombres.append(m["name"])  # ej: "models/gemini-2.5-flash"
    # Preferimos los "flash" (rápidos y gratis), sin versiones raras
    favoritos = ["models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-flash-latest",
                 "models/gemini-2.5-flash-lite", "models/gemini-2.0-flash-lite", "models/gemini-flash-lite-latest"]
    def puntaje(n):
        if n in favoritos:
            return -100 + favoritos.index(n)
        p = 0
        if "pro" in n: p += 8
        if "flash" in n: p -= 10
        if "lite" in n: p += 2
        for malo in ("tts", "image", "live", "audio", "embedding", "thinking", "exp", "preview", "vision"):
            if malo in n: p += 20
        if n.startswith("models/gemma"): p += 5
        return p
    return sorted(nombres, key=puntaje)


def preguntar_a_la_ia(clave, historial):
    clave = clave.strip()
    contenidos = [
        {"role": "user" if m["rol"] == "usuario" else "model", "parts": [{"text": m["texto"]}]}
        for m in historial
    ]
    def cuerpo_para(modelo):
        datos = {"system_instruction": {"parts": [{"text": INSTRUCCION}]}, "contents": contenidos}
        if "2.5-flash" in modelo:
            datos["generationConfig"] = {"thinkingConfig": {"thinkingBudget": 0}}
        return json.dumps(datos).encode()
    modelos = modelos_disponibles(clave)
    if not modelos:
        raise RuntimeError(": tu clave no tiene ningún modelo de chat disponible. "
                           "Crea una clave nueva en aistudio.google.com/apikey.")
    ultimo_error = None
    for modelo in modelos[:6]:
        try:
            r = _pedir(f"{BASE}/{modelo}:generateContent", clave, cuerpo_para(modelo))
            return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
        except RuntimeError as e:
            ultimo_error = e
            if str(e).startswith(("(401)", "(403)")):
                break
    raise ultimo_error

st.set_page_config(page_title="Francheska · Asistente Personal", page_icon="🦋")

with st.sidebar:
    st.header("⚙️ Ajustes")
    clave = st.text_input("Clave de API de Google Gemini", type="password")
    st.markdown("Consíguela gratis en [aistudio.google.com/apikey](https://aistudio.google.com/apikey)")
    if st.button("🗑️ Borrar conversación"):
        st.session_state.mensajes = []

st.title("🦋 Francheska")
st.caption("Tu asistente personal · pregúntame lo que quieras")

if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

for m in st.session_state.mensajes:
    with st.chat_message("user" if m["rol"] == "usuario" else "assistant", avatar="🙂" if m["rol"] == "usuario" else "🌸"):
        st.markdown(m["texto"])

pregunta = st.chat_input("Escribe tu pregunta...")
if pregunta:
    with st.chat_message("user", avatar="🙂"):
        st.markdown(pregunta)
    if not clave:
        st.warning("Primero pega tu clave de API en el menú de la izquierda.")
    else:
        st.session_state.mensajes.append({"rol": "usuario", "texto": pregunta})
        with st.chat_message("assistant", avatar="🌸"):
            with st.spinner("Pensando..."):
                try:
                    texto = preguntar_a_la_ia(clave, st.session_state.mensajes)
                    st.markdown(texto)
                    st.session_state.mensajes.append({"rol": "ia", "texto": texto})
                except RuntimeError as e:
                    st.session_state.mensajes.pop()
                    st.error(f"Error de la IA {e}")
                except Exception as e:
                    st.session_state.mensajes.pop()
                    st.error(f"No se pudo conectar: {e}")
