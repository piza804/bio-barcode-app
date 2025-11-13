import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import streamlit.components.v1 as components

# --- Firebase初期化 ---
if not firebase_admin._apps:
    try:
        firebase_secrets = dict(st.secrets["firebase"])
        firebase_secrets["private_key"] = firebase_secrets["private_key"].replace("\\n", "\n")
        with open("firebase_key.json", "w") as f:
            json.dump(firebase_secrets, f)
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase初期化エラー: {e}")
        st.stop()
db = firestore.client()

st.title("📱 スマホ対応バーコードスキャン")

# --- QuaggaJS HTMLを埋め込み ---
quagga_html = """
<div id="barcode-scanner" style="width:100%; max-width:480px; margin:auto;">
  <video id="video" width="100%" autoplay muted playsinline></video>
  <p id="barcode-result" style="font-weight:bold; text-align:center; margin-top:1rem;">バーコード未検出</p>
</div>
<script src="https://unpkg.com/@ericblade/quagga2@v0.0.9/dist/quagga.min.js"></script>
<script>
const resultElem = document.getElementById('barcode-result');
Quagga.init({
  inputStream: {
    type: "LiveStream",
    constraints: {
      facingMode: "environment",
    },
    target: document.querySelector('#barcode-scanner')
  },
  decoder: {
    readers: ["code_128_reader", "ean_reader", "ean_8_reader", "upc_reader", "upc_e_reader"]
  }
}, function(err) {
  if (err) {
    resultElem.textContent = "カメラ初期化エラー: " + err;
    return;
  }
  Quagga.start();
});

Quagga.onDetected(function(data) {
  const code = data.codeResult.code;
  resultElem.textContent = "検出: " + code;
  window.parent.postMessage({type: 'barcode', value: code}, '*');
});
</script>
"""

components.html(quagga_html, height=600)

# --- JSから受信 ---
barcode_value = st.experimental_get_query_params().get("barcode", [""])[0]
if barcode_value:
    st.success(f"バーコード読み取り成功: {barcode_value}")
